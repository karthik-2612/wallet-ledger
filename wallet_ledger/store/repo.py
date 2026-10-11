"""Queries. Every function takes a Connection that is already inside a transaction; the
caller (the service layer) decides transaction boundaries."""

from sqlalchemy import Connection, RowMapping, insert, select, update

from wallet_ledger.store.tables import accounts, api_keys, idempotency_keys, transactions, transfers


def insert_api_key(conn: Connection, name: str, key_hash: str, created_at: str) -> int:
    result = conn.execute(
        insert(api_keys).values(name=name, key_hash=key_hash, created_at=created_at)
    )
    return result.inserted_primary_key[0]


def find_api_key_id(conn: Connection, key_hash: str) -> int | None:
    return conn.execute(
        select(api_keys.c.id).where(api_keys.c.key_hash == key_hash)
    ).scalar_one_or_none()


def insert_account(conn: Connection, **values: object) -> None:
    conn.execute(insert(accounts).values(**values))


def get_account(conn: Connection, account_id: str) -> RowMapping | None:
    return conn.execute(select(accounts).where(accounts.c.id == account_id)).mappings().first()


def apply_delta(conn: Connection, account_id: str, delta: int, max_balance: int) -> int | None:
    """Atomically add `delta` to the balance. Returns the new balance, or None if the
    result would fall outside [0, max_balance] (the row is then left unchanged)."""
    new_balance = accounts.c.balance + delta
    stmt = (
        update(accounts)
        .where(accounts.c.id == account_id, new_balance >= 0, new_balance <= max_balance)
        .values(balance=new_balance)
        .returning(accounts.c.balance)
    )
    return conn.execute(stmt).scalar_one_or_none()


def insert_transaction(conn: Connection, **values: object) -> int:
    return conn.execute(insert(transactions).values(**values)).inserted_primary_key[0]


def get_transaction(conn: Connection, transaction_id: int) -> RowMapping | None:
    stmt = select(transactions).where(transactions.c.id == transaction_id)
    return conn.execute(stmt).mappings().first()


def list_transactions(
    conn: Connection, account_id: str, limit: int, before_id: int | None
) -> list[RowMapping]:
    stmt = select(transactions).where(transactions.c.account_id == account_id)
    if before_id is not None:
        stmt = stmt.where(transactions.c.id < before_id)
    stmt = stmt.order_by(transactions.c.id.desc()).limit(limit)
    return list(conn.execute(stmt).mappings())


def insert_transfer(conn: Connection, **values: object) -> None:
    conn.execute(insert(transfers).values(**values))


def get_transfer(conn: Connection, transfer_id: str) -> RowMapping | None:
    return conn.execute(select(transfers).where(transfers.c.id == transfer_id)).mappings().first()


def get_idempotency_record(conn: Connection, api_key_id: int, key: str) -> RowMapping | None:
    stmt = select(idempotency_keys).where(
        idempotency_keys.c.api_key_id == api_key_id, idempotency_keys.c.key == key
    )
    return conn.execute(stmt).mappings().first()


def insert_idempotency_record(conn: Connection, **values: object) -> None:
    conn.execute(insert(idempotency_keys).values(**values))
