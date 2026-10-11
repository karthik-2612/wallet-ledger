"""Minimal forward/backward migration runner for the numbered SQL files in migrations/."""

import re
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy import Engine

MIGRATIONS_DIR = Path(__file__).resolve().parent.parent / "migrations"
_FILENAME = re.compile(r"^(\d{4})_([a-z0-9_]+)\.(up|down)\.sql$")


@dataclass(frozen=True)
class Migration:
    version: int
    name: str
    up: str
    down: str


def load_migrations(directory: Path = MIGRATIONS_DIR) -> list[Migration]:
    parts: dict[tuple[int, str], dict[str, str]] = {}
    for path in sorted(directory.glob("*.sql")):
        match = _FILENAME.match(path.name)
        if match is None:
            raise ValueError(f"bad migration filename: {path.name}")
        version, name, direction = int(match[1]), match[2], match[3]
        parts.setdefault((version, name), {})[direction] = path.read_text()

    migrations = []
    for (version, name), sql in sorted(parts.items()):
        if set(sql) != {"up", "down"}:
            raise ValueError(f"migration {version:04d}_{name} needs both .up.sql and .down.sql")
        migrations.append(Migration(version, name, sql["up"], sql["down"]))

    versions = [m.version for m in migrations]
    if versions != list(range(1, len(migrations) + 1)):
        raise ValueError(f"migration versions must be unique and contiguous from 1: {versions}")
    return migrations


def migrate(engine: Engine, target: int | None = None, directory: Path = MIGRATIONS_DIR) -> int:
    """Apply or roll back migrations until the schema is at `target` (default: latest).
    Each migration runs in its own transaction together with its bookkeeping row."""
    migrations = load_migrations(directory)
    target = len(migrations) if target is None else target
    if not 0 <= target <= len(migrations):
        raise ValueError(f"target must be between 0 and {len(migrations)}, got {target}")

    raw = engine.raw_connection()
    try:
        db = raw.driver_connection
        db.execute(
            "CREATE TABLE IF NOT EXISTS schema_migrations "
            "(version INTEGER PRIMARY KEY, applied_at TEXT NOT NULL)"
        )
        current = db.execute("SELECT COALESCE(MAX(version), 0) FROM schema_migrations").fetchone()[
            0
        ]
        if current > len(migrations):
            raise RuntimeError(f"database is at version {current}, newer than this code")

        now = datetime.now(UTC).isoformat()
        for m in migrations[current:target]:
            _run_script(db, m.up, f"INSERT INTO schema_migrations VALUES ({m.version}, '{now}')")
        for m in reversed(migrations[target:current]):
            _run_script(db, m.down, f"DELETE FROM schema_migrations WHERE version = {m.version}")
        return target
    finally:
        raw.close()


def _run_script(db, sql: str, bookkeeping: str) -> None:
    try:
        db.executescript(f"BEGIN IMMEDIATE;\n{sql}\n;\n{bookkeeping};\nCOMMIT;")
    except Exception:
        if db.in_transaction:
            db.execute("ROLLBACK")
        raise
