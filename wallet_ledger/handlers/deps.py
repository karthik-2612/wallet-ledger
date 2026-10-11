"""Shared FastAPI dependencies."""

from typing import Annotated

from fastapi import Depends, Header, Request, Security
from fastapi.security import APIKeyHeader

from wallet_ledger.service.auth import AuthService
from wallet_ledger.service.errors import Unauthenticated
from wallet_ledger.service.ledger import LedgerService

_api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


def _ledger(request: Request) -> LedgerService:
    return request.app.state.ledger


def _owner(request: Request, raw_key: Annotated[str | None, Security(_api_key_header)]) -> int:
    if not raw_key:
        raise Unauthenticated("missing X-API-Key header")
    auth: AuthService = request.app.state.auth
    return auth.authenticate(raw_key)


Ledger = Annotated[LedgerService, Depends(_ledger)]
Owner = Annotated[int, Depends(_owner)]
IdempotencyKey = Annotated[
    str | None,
    Header(
        alias="Idempotency-Key",
        min_length=1,
        max_length=255,
        description="Retries with the same key and body return the original result",
    ),
]
