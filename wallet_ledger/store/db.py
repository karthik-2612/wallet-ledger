"""Engine construction and per-connection SQLite setup."""

from sqlalchemy import Engine, create_engine, event

DEFAULT_DATABASE_URL = "sqlite:///./wallet.db"


def make_engine(url: str = DEFAULT_DATABASE_URL) -> Engine:
    if not url.startswith("sqlite:///") or url.endswith(":memory:"):
        raise ValueError("a file-backed sqlite:/// URL is required")
    engine = create_engine(url, connect_args={"check_same_thread": False, "timeout": 30})

    @event.listens_for(engine, "connect")
    def _on_connect(dbapi_conn, _record) -> None:
        # Disable the driver's implicit transactions so the "begin" hook below owns them.
        dbapi_conn.isolation_level = None
        dbapi_conn.execute("PRAGMA foreign_keys = ON")

    @event.listens_for(engine, "begin")
    def _on_begin(conn) -> None:
        # Take SQLite's write lock up front: a read-check-write sequence (e.g. idempotency
        # lookup, then insert) can never interleave with another writer.
        conn.exec_driver_sql("BEGIN IMMEDIATE")

    return engine
