-- Records which resource a (caller, Idempotency-Key) pair produced, so retries
-- replay the original result instead of moving money twice.
CREATE TABLE idempotency_keys (
    api_key_id    INTEGER NOT NULL REFERENCES api_keys (id),
    key           TEXT    NOT NULL,
    fingerprint   TEXT    NOT NULL,
    resource_type TEXT    NOT NULL CHECK (resource_type IN ('transaction', 'transfer')),
    resource_id   TEXT    NOT NULL,
    created_at    TEXT    NOT NULL,
    PRIMARY KEY (api_key_id, key)
);
