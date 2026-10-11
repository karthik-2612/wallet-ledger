"""API keys. Only a SHA-256 hash of each key is stored; the raw key is shown once."""

import hashlib
import secrets
from datetime import UTC, datetime

from sqlalchemy import Engine

from wallet_ledger.service.errors import Unauthenticated
from wallet_ledger.store import repo


def hash_key(raw_key: str) -> str:
    return hashlib.sha256(raw_key.encode()).hexdigest()


class AuthService:
    def __init__(self, engine: Engine) -> None:
        self._engine = engine

    def create_api_key(self, name: str) -> str:
        raw_key = "wl_" + secrets.token_urlsafe(32)
        with self._engine.begin() as conn:
            repo.insert_api_key(conn, name, hash_key(raw_key), datetime.now(UTC).isoformat())
        return raw_key

    def authenticate(self, raw_key: str) -> int:
        """Return the id of the key that owns the request, or raise Unauthenticated."""
        with self._engine.begin() as conn:
            key_id = repo.find_api_key_id(conn, hash_key(raw_key))
        if key_id is None:
            raise Unauthenticated("invalid API key")
        return key_id
