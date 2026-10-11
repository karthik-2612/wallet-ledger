import pytest


@pytest.mark.parametrize(
    ("method", "path", "body"),
    [
        ("post", "/accounts", {"currency": "USD"}),
        ("get", "/accounts/acc_x", None),
        ("post", "/accounts/acc_x/deposit", {"amount": 1}),
        ("post", "/accounts/acc_x/withdraw", {"amount": 1}),
        ("post", "/transfers", {"from_account_id": "a", "to_account_id": "b", "amount": 1}),
        ("get", "/accounts/acc_x/transactions", None),
    ],
)
@pytest.mark.parametrize(
    ("headers", "message"),
    [
        ({}, "missing X-API-Key header"),
        ({"X-API-Key": "wl_not-a-real-key"}, "invalid API key"),
    ],
)
def test_every_endpoint_requires_a_valid_key(client, method, path, body, headers, message):
    resp = client.request(method, path, json=body, headers=headers)
    assert resp.status_code == 401
    assert resp.json()["error"] == {"code": "unauthenticated", "message": message}


@pytest.mark.parametrize(
    ("method", "path_template", "body"),
    [
        ("get", "/accounts/{id}", None),
        ("post", "/accounts/{id}/deposit", {"amount": 1}),
        ("post", "/accounts/{id}/withdraw", {"amount": 1}),
        ("get", "/accounts/{id}/transactions", None),
    ],
)
def test_keys_cannot_touch_accounts_they_do_not_own(alice, bob, method, path_template, body):
    account = alice.account(balance=10)
    resp = bob.client.request(
        method, path_template.format(id=account), json=body, headers={"X-API-Key": bob.key}
    )
    assert resp.status_code == 404
    assert alice.balance(account) == 10


def test_cannot_transfer_out_of_someone_elses_account(alice, bob):
    source = alice.account(balance=10)
    dest = bob.account()
    resp = bob.post("/transfers", {"from_account_id": source, "to_account_id": dest, "amount": 5})
    assert resp.status_code == 404
    assert alice.balance(source) == 10
    assert bob.balance(dest) == 0
