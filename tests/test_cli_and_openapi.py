from pathlib import Path

import pytest
import yaml
from fastapi.testclient import TestClient

from wallet_ledger.app import create_app
from wallet_ledger.cli import main

OPENAPI_FILE = Path(__file__).resolve().parent.parent / "openapi.yaml"


def test_openapi_yaml_is_up_to_date(app):
    committed = yaml.safe_load(OPENAPI_FILE.read_text())
    assert committed == app.openapi(), "regenerate with: wallet-ledger openapi > openapi.yaml"


def test_cli_openapi_prints_spec(db_url, capsys):
    assert main(["--db", db_url, "openapi"]) == 0
    assert yaml.safe_load(capsys.readouterr().out)["info"]["title"] == "Wallet Ledger"


def test_cli_migrate_and_create_key(db_url, capsys):
    assert main(["--db", db_url, "migrate", "--to", "1"]) == 0
    assert "version 1" in capsys.readouterr().out
    assert main(["--db", db_url, "create-key", "ops"]) == 0
    key = capsys.readouterr().out.strip()
    assert key.startswith("wl_")

    with TestClient(create_app(db_url)) as client:
        resp = client.post("/accounts", json={"currency": "USD"}, headers={"X-API-Key": key})
    assert resp.status_code == 201


@pytest.mark.parametrize("url", ["postgresql://x/y", "sqlite:///:memory:"])
def test_only_file_sqlite_urls_are_accepted(url):
    with pytest.raises(ValueError, match="sqlite"):
        create_app(url)


def test_unknown_route_uses_error_shape(client):
    resp = client.get("/nope")
    assert resp.status_code == 404
    assert resp.json() == {"error": {"code": "http_error", "message": "Not Found"}}


def test_malformed_json_is_a_validation_error(alice):
    resp = alice.client.post(
        "/accounts",
        content=b"{not json",
        headers={"X-API-Key": alice.key, "Content-Type": "application/json"},
    )
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "validation_error"
