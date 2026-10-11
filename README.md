# Wallet Ledger

A small wallet ledger REST API: Python 3.12, FastAPI, SQLAlchemy (Core) and SQLite.

- Amounts are integer minor units (e.g. cents). Balances never go negative.
- Transfers are atomic: debit, credit and both ledger entries commit in one transaction.
- `POST /accounts/{id}/deposit`, `/withdraw` and `POST /transfers` accept an `Idempotency-Key` header.
- Every request needs an `X-API-Key`. Each key owns the accounts it created.

See [openapi.yaml](openapi.yaml) for the API and [CONVENTIONS.md](CONVENTIONS.md) for how the code is organised.

## Run

```bash
uv sync
```

```bash
uv run wallet-ledger create-key my-app
```

```bash
uv run uvicorn wallet_ledger.app:create_app --factory --reload
```

The database defaults to `./wallet.db`; set `WALLET_DB_URL=sqlite:////abs/path.db` to change it. Migrations run on startup, or explicitly with `uv run wallet-ledger migrate [--to N]`.

## Example

```bash
curl -s -X POST localhost:8000/accounts -H "X-API-Key: $KEY" -H 'Content-Type: application/json' -d '{"currency":"USD"}'
```

```bash
curl -s -X POST localhost:8000/accounts/$ACC/deposit -H "X-API-Key: $KEY" -H 'Idempotency-Key: dep-1' -H 'Content-Type: application/json' -d '{"amount":1500}'
```

## Check

```bash
uv run ruff check . && uv run ruff format --check . && uv run pytest
```
