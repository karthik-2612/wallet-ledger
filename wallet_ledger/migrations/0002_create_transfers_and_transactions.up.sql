CREATE TABLE transfers (
    id              TEXT    PRIMARY KEY,
    from_account_id TEXT    NOT NULL REFERENCES accounts (id),
    to_account_id   TEXT    NOT NULL REFERENCES accounts (id),
    amount          INTEGER NOT NULL CHECK (typeof(amount) = 'integer' AND amount > 0),
    currency        TEXT    NOT NULL,
    created_at      TEXT    NOT NULL,
    CHECK (from_account_id <> to_account_id)
);

-- One row per balance change. AUTOINCREMENT guarantees ids are never reused,
-- which keeps the id-based pagination cursor stable.
CREATE TABLE transactions (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    account_id    TEXT    NOT NULL REFERENCES accounts (id),
    type          TEXT    NOT NULL
                  CHECK (type IN ('deposit', 'withdrawal', 'transfer_in', 'transfer_out')),
    amount        INTEGER NOT NULL CHECK (typeof(amount) = 'integer' AND amount > 0),
    balance_after INTEGER NOT NULL CHECK (typeof(balance_after) = 'integer' AND balance_after >= 0),
    transfer_id   TEXT    REFERENCES transfers (id),
    created_at    TEXT    NOT NULL,
    CHECK ((type IN ('transfer_in', 'transfer_out')) = (transfer_id IS NOT NULL))
);

CREATE INDEX idx_transactions_account_id ON transactions (account_id, id);
