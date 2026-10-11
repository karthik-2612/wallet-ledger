"""Application factory. Run with: uvicorn wallet_ledger.app:create_app --factory"""

import os
from contextlib import asynccontextmanager

from fastapi import FastAPI

from wallet_ledger.handlers import accounts, transfers
from wallet_ledger.handlers.errors import install_error_handlers
from wallet_ledger.service.auth import AuthService
from wallet_ledger.service.ledger import LedgerService
from wallet_ledger.store.db import DEFAULT_DATABASE_URL, make_engine
from wallet_ledger.store.migrate import migrate


def create_app(database_url: str | None = None) -> FastAPI:
    engine = make_engine(database_url or os.environ.get("WALLET_DB_URL", DEFAULT_DATABASE_URL))

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        migrate(engine)
        yield
        engine.dispose()

    app = FastAPI(title="Wallet Ledger", version="0.1.0", lifespan=lifespan)
    app.state.ledger = LedgerService(engine)
    app.state.auth = AuthService(engine)
    install_error_handlers(app)
    app.include_router(accounts.router)
    app.include_router(transfers.router)
    return app
