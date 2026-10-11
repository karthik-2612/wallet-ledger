import pytest


def test_create_and_get_account(alice):
    resp = alice.post("/accounts", {"currency": "EUR"})
    assert resp.status_code == 201
    body = resp.json()
    assert body["id"].startswith("acc_")
    assert body["currency"] == "EUR"
    assert body["balance"] == 0

    fetched = alice.get(f"/accounts/{body['id']}")
    assert fetched.status_code == 200
    assert fetched.json() == body


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"currency": "usd"},
        {"currency": "US"},
        {"currency": "USDX"},
        {"currency": 840},
        {"currency": "USD", "balance": 100},
    ],
)
def test_create_account_rejects_invalid_body(alice, payload):
    resp = alice.post("/accounts", payload)
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "validation_error"


def test_get_missing_account_is_404(alice):
    resp = alice.get("/accounts/acc_missing")
    assert resp.status_code == 404
    assert resp.json()["error"] == {"code": "not_found", "message": "account acc_missing not found"}


def test_list_transactions_newest_first_with_cursor_pagination(alice):
    account = alice.account()
    for amount in (1, 2, 3, 4, 5):
        alice.post(f"/accounts/{account}/deposit", {"amount": amount})
    alice.post(f"/accounts/{account}/withdraw", {"amount": 6})

    first = alice.get(f"/accounts/{account}/transactions", limit=4).json()
    assert [t["amount"] for t in first["data"]] == [6, 5, 4, 3]
    assert [t["type"] for t in first["data"]] == ["withdrawal", "deposit", "deposit", "deposit"]
    assert first["data"][0]["balance_after"] == 9
    assert first["next_before_id"] == first["data"][-1]["id"]

    second = alice.get(
        f"/accounts/{account}/transactions", limit=4, before_id=first["next_before_id"]
    ).json()
    assert [t["amount"] for t in second["data"]] == [2, 1]
    assert second["next_before_id"] is None


def test_list_transactions_empty(alice):
    account = alice.account()
    body = alice.get(f"/accounts/{account}/transactions").json()
    assert body == {"data": [], "next_before_id": None}


@pytest.mark.parametrize("params", [{"limit": 0}, {"limit": 101}, {"before_id": 0}])
def test_list_transactions_rejects_bad_query(alice, params):
    account = alice.account()
    assert alice.get(f"/accounts/{account}/transactions", **params).status_code == 422
