import sqlite3

import pytest

from wallet_ledger.store.db import make_engine
from wallet_ledger.store.migrate import MIGRATIONS_DIR, load_migrations, migrate
from wallet_ledger.store.tables import metadata


@pytest.fixture
def engine(db_url):
    engine = make_engine(db_url)
    yield engine
    engine.dispose()


def tables(engine) -> set[str]:
    with engine.connect() as conn:
        rows = conn.exec_driver_sql("SELECT name FROM sqlite_master WHERE type = 'table'")
        return {r[0] for r in rows} - {"schema_migrations", "sqlite_sequence"}


def version(engine) -> int:
    with engine.connect() as conn:
        return conn.exec_driver_sql(
            "SELECT COALESCE(MAX(version), 0) FROM schema_migrations"
        ).scalar()


def test_every_migration_has_up_and_down():
    migrations = load_migrations()
    assert [m.version for m in migrations] == list(range(1, len(migrations) + 1))
    assert all(m.up.strip() and m.down.strip() for m in migrations)


def test_up_down_up_round_trip(engine):
    latest = len(load_migrations())
    assert migrate(engine) == latest
    assert tables(engine) == set(metadata.tables)

    for target in range(latest - 1, -1, -1):
        migrate(engine, target)
        assert version(engine) == target
    assert tables(engine) == set()

    migrate(engine)
    assert tables(engine) == set(metadata.tables)


def test_migrate_is_idempotent(engine):
    migrate(engine)
    assert migrate(engine) == len(load_migrations())


def test_table_definitions_match_migrated_schema(engine):
    migrate(engine)
    with engine.connect() as conn:
        for table in metadata.sorted_tables:
            rows = conn.exec_driver_sql(f"PRAGMA table_info({table.name})").all()
            assert [r[1] for r in rows] == [c.name for c in table.columns], table.name


def test_schema_constraints_back_up_the_service(engine):
    migrate(engine)
    db = sqlite3.connect(engine.url.database)
    db.execute("PRAGMA foreign_keys = ON")
    db.execute("INSERT INTO api_keys VALUES (1, 'k', 'h', 'now')")
    db.execute("INSERT INTO accounts VALUES ('a', 1, 'USD', 0, 'now')")
    for bad in [
        "UPDATE accounts SET balance = -1",
        "UPDATE accounts SET balance = 1.5",
        "INSERT INTO accounts VALUES ('b', 99, 'USD', 0, 'now')",
        "INSERT INTO accounts VALUES ('c', 1, 'usd', 0, 'now')",
        "INSERT INTO transactions (account_id, type, amount, balance_after, created_at)"
        " VALUES ('a', 'transfer_in', 1, 1, 'now')",
    ]:
        with pytest.raises(sqlite3.IntegrityError):
            db.execute(bad)
    db.close()


def write(directory, name, sql="SELECT 1;"):
    (directory / name).write_text(sql)


@pytest.mark.parametrize(
    ("files", "error"),
    [
        (["0001_a.up.sql"], "needs both"),
        (["0001_a.up.sql", "0001_a.down.sql", "0003_c.up.sql", "0003_c.down.sql"], "contiguous"),
        (["1_a.up.sql"], "bad migration filename"),
    ],
)
def test_load_rejects_malformed_directories(tmp_path, files, error):
    for name in files:
        write(tmp_path, name)
    with pytest.raises(ValueError, match=error):
        load_migrations(tmp_path)


def test_failed_migration_rolls_back_completely(engine, tmp_path):
    write(tmp_path, "0001_ok.up.sql", "CREATE TABLE ok (id INTEGER);")
    write(tmp_path, "0001_ok.down.sql", "DROP TABLE ok;")
    write(tmp_path, "0002_bad.up.sql", "CREATE TABLE half (id INTEGER); NOT VALID SQL;")
    write(tmp_path, "0002_bad.down.sql", "DROP TABLE half;")
    with pytest.raises(sqlite3.OperationalError):
        migrate(engine, directory=tmp_path)
    assert tables(engine) == {"ok"}
    assert version(engine) == 1


def test_rejects_out_of_range_target_and_newer_database(engine, tmp_path):
    with pytest.raises(ValueError, match="target"):
        migrate(engine, 99)
    migrate(engine)
    write(tmp_path, "0001_a.up.sql")
    write(tmp_path, "0001_a.down.sql")
    with pytest.raises(RuntimeError, match="newer"):
        migrate(engine, directory=tmp_path)


def test_migrations_dir_ships_with_package():
    assert MIGRATIONS_DIR.is_dir()
