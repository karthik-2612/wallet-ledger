# Conventions

Rules for changing this codebase. If a change needs to break one, update this file in the same PR and say why.

## Layering

```
handlers/  →  service/  →  store/  →  SQLite
                              ↑
                         migrations/
```

Imports only point down the diagram. `store` never imports `service` or `handlers`, and `service` never imports `handlers`, FastAPI or Starlette.

| Layer | Owns | Must not |
|---|---|---|
| `handlers/` | Routes, request/response schemas, auth dependency, mapping errors to HTTP | Contain business rules, open transactions, or touch `store` directly |
| `service/` | Business rules, transaction boundaries, idempotency, domain models and errors | Know about HTTP status codes, headers or Pydantic schemas |
| `store/` | Engine setup, table definitions, queries, the migration runner | Enforce business rules beyond what a single SQL statement guarantees |
| `migrations/` | The schema, as numbered SQL files | Be edited after they have been merged |

- **One public service method = one transaction.** Each method opens exactly one `engine.begin()` block, and every read and write that a decision depends on happens inside it. Repo functions take a `Connection` and never commit.
- **Validate in both places.** Handlers validate request shape with Pydantic (types, ranges, `extra="forbid"`). The service re-checks domain invariants such as amount bounds and doesn't assume its caller is the HTTP layer.
- **Store returns rows; service returns domain models.** The service converts `RowMapping`s into the dataclasses in `service/models.py`. Handlers declare a `response_model` from `handlers/schemas.py`, so a field added to a dataclass never leaks into the API by accident.

## Money

- Amounts and balances are `int` minor units, end to end. No floats or `Decimal` anywhere, and JSON amounts are parsed with `strict=True`, so `10.0`, `"10"` and `true` are rejected.
- Never read a balance, compute in Python, then write it back. Balance changes go through `repo.apply_delta`, a single conditional `UPDATE … WHERE balance + :delta BETWEEN 0 AND :max … RETURNING balance`. If it returns `None`, the change was refused and nothing was written.
- Every balance change writes exactly one `transactions` row recording `balance_after`. A transfer writes two rows (`transfer_out`, `transfer_in`) and one `transfers` row, all in the same transaction.
- The schema enforces the same invariants as the code: `CHECK (balance >= 0)`, `typeof(...) = 'integer'`, foreign keys. These checks are a backstop, not the primary check; the service should never rely on hitting one.

## Idempotency

- `Idempotency-Key` is scoped per API key. It is stored in the same transaction as the money movement, so either both commit or neither does.
- Only successful results are stored. A request that fails (e.g. insufficient funds) does not use up its key, so the client can retry it with the same key.
- A replay returns the stored resource, re-read from the database. A key reused with a different request fingerprint (operation, accounts, amount) gets `422 idempotency_key_reused`.
- New mutating endpoints that move money must take `IdempotencyKey` and go through `LedgerService._idempotent`.

## Error handling

- Business failures are raised as a subclass of `service.errors.DomainError` with a stable snake_case `code`. Never raise `HTTPException` from the service, and never return error values instead of raising.
- `handlers/errors.py` is the only place that maps errors to status codes: `Unauthenticated` → 401, `NotFound` → 404, every other `DomainError` → 422. A new error class needs a new entry there only if it needs a different status.
- Every error response has the same shape: `{"error": {"code": "...", "message": "...", "details"?: [...]}}`. Validation errors use `code: "validation_error"` and list the failing fields in `details`.
- An account owned by another API key returns `404 not_found`, exactly like a missing one, so callers can't probe which ids exist. The one exception is a transfer's destination, which may belong to any key.
- Don't catch broad `Exception` in handlers or the service. Unexpected errors should propagate (500) and roll back the transaction.
- `code` values and the response shape are part of the API contract. Changing them is a breaking change.

## Migrations

- Files live in `wallet_ledger/migrations/` and are named `NNNN_snake_case_name.up.sql` plus a matching `.down.sql`. Versions are contiguous from `0001`; `load_migrations()` refuses anything else.
- **Never edit a merged migration.** Add a new one instead. A down migration must restore the exact schema of the previous version.
- Each migration runs in its own transaction along with its `schema_migrations` row. Don't put `BEGIN`/`COMMIT`, or `PRAGMA`s that can't run inside a transaction, in migration files.
- Drop child tables and indexes before the tables they reference.
- After changing the schema, update `store/tables.py` to match. `test_table_definitions_match_migrated_schema` fails if they drift. Never use `metadata.create_all()`.
- Migrations run automatically on app startup and through `wallet-ledger migrate [--to N]`.

## Testing

- Every behaviour change ships with tests. CI fails below 90% line coverage, and new code should be fully covered.
- Prefer table-driven tests (`pytest.mark.parametrize`) that list inputs and expected outcomes, over near-duplicate test functions.
- Test through the HTTP API with `TestClient` by default. Use the `alice`/`bob` fixtures from `tests/conftest.py` for callers with separate API keys. Call the service directly only for rules that HTTP validation would hide.
- A rejected money movement must assert both the error `code` and that balances and the transaction history are unchanged.
- Each test gets its own SQLite file in `tmp_path`, never a shared database or `:memory:`.
- Concurrency-sensitive rules (no overdraft, one application per idempotency key) have threaded tests. Keep them deterministic by asserting on final state, not on timing.
- `openapi.yaml` is generated, and a test fails if it is stale. Regenerate it after any API change:

  ```bash
  uv run wallet-ledger openapi > openapi.yaml
  ```

- Before pushing, run the same checks as CI:

  ```bash
  uv run ruff check . && uv run ruff format --check . && uv run pytest
  ```
