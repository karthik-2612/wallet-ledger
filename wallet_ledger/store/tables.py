"""Query-side table definitions. The SQL migrations own the schema; these must mirror them
(tests/test_migrations.py checks that they do). Never call metadata.create_all()."""

from sqlalchemy import Column, Integer, MetaData, Table, Text

metadata = MetaData()

api_keys = Table(
    "api_keys",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("name", Text),
    Column("key_hash", Text),
    Column("created_at", Text),
)

accounts = Table(
    "accounts",
    metadata,
    Column("id", Text, primary_key=True),
    Column("owner_key_id", Integer),
    Column("currency", Text),
    Column("balance", Integer),
    Column("created_at", Text),
)

transfers = Table(
    "transfers",
    metadata,
    Column("id", Text, primary_key=True),
    Column("from_account_id", Text),
    Column("to_account_id", Text),
    Column("amount", Integer),
    Column("currency", Text),
    Column("created_at", Text),
)

transactions = Table(
    "transactions",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("account_id", Text),
    Column("type", Text),
    Column("amount", Integer),
    Column("balance_after", Integer),
    Column("transfer_id", Text),
    Column("created_at", Text),
)

idempotency_keys = Table(
    "idempotency_keys",
    metadata,
    Column("api_key_id", Integer, primary_key=True),
    Column("key", Text, primary_key=True),
    Column("fingerprint", Text),
    Column("resource_type", Text),
    Column("resource_id", Text),
    Column("created_at", Text),
)
