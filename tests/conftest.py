from dataclasses import dataclass

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from wallet_ledger.app import create_app


@dataclass
class Caller:
    """A TestClient bound to one API key."""

    client: TestClient
    key: str

    def _headers(self, idem_key: str | None) -> dict[str, str]:
        headers = {"X-API-Key": self.key}
        if idem_key is not None:
            headers["Idempotency-Key"] = idem_key
        return headers

    def get(self, path: str, **params):
        return self.client.get(path, params=params, headers=self._headers(None))

    def post(self, path: str, json: dict, idem_key: str | None = None):
        return self.client.post(path, json=json, headers=self._headers(idem_key))

    def account(self, currency: str = "USD", balance: int = 0) -> str:
        account_id = self.post("/accounts", {"currency": currency}).json()["id"]
        if balance:
            assert (
                self.post(f"/accounts/{account_id}/deposit", {"amount": balance}).status_code == 201
            )
        return account_id

    def balance(self, account_id: str) -> int:
        return self.get(f"/accounts/{account_id}").json()["balance"]


@pytest.fixture
def db_url(tmp_path) -> str:
    return f"sqlite:///{tmp_path / 'test.db'}"


@pytest.fixture
def app(db_url) -> FastAPI:
    return create_app(db_url)


@pytest.fixture
def client(app):
    with TestClient(app) as client:
        yield client


@pytest.fixture
def make_caller(app, client):
    def make(name: str = "test") -> Caller:
        return Caller(client, app.state.auth.create_api_key(name))

    return make


@pytest.fixture
def alice(make_caller) -> Caller:
    return make_caller("alice")


@pytest.fixture
def bob(make_caller) -> Caller:
    return make_caller("bob")
