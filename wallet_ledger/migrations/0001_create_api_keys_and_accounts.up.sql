CREATE TABLE api_keys (
    id         INTEGER PRIMARY KEY,
    name       TEXT    NOT NULL,
    key_hash   TEXT    NOT NULL UNIQUE,
    created_at TEXT    NOT NULL
);

CREATE TABLE accounts (
    id           TEXT    PRIMARY KEY,
    owner_key_id INTEGER NOT NULL REFERENCES api_keys (id),
    currency     TEXT    NOT NULL CHECK (length(currency) = 3 AND currency = upper(currency)),
    balance      INTEGER NOT NULL DEFAULT 0
                 CHECK (typeof(balance) = 'integer'
                        AND balance >= 0
                        AND balance <= 1000000000000000000),
    created_at   TEXT    NOT NULL
);

CREATE INDEX idx_accounts_owner_key_id ON accounts (owner_key_id);
