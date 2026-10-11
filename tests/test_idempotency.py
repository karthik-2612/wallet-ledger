import threading

import pytest


@pytest.fixture
def accounts(alice):
    return alice.account(balance=100), alice.account()


@pytest.fixture
def requests(accounts):
    """(path, first body, conflicting body) for every idempotent endpoint."""
    source, dest = accounts
    transfer = {"from_account_id": source, "to_account_id": dest, "amount": 10}
    return {
        "deposit": (f"/accounts/{source}/deposit", {"amount": 10}, {"amount": 11}),
        "withdraw": (f"/accounts/{source}/withdraw", {"amount": 10}, {"amount": 11}),
        "transfer": ("/transfers", transfer, transfer | {"amount": 11}),
    }


ENDPOINTS = ["deposit", "withdraw", "transfer"]


@pytest.mark.parametrize("endpoint", ENDPOINTS)
def test_retry_replays_original_result_without_moving_money_again(
    alice, accounts, requests, endpoint
):
    path, body, _ = requests[endpoint]
    first = alice.post(path, body, idem_key="k1")
    balances = [alice.balance(a) for a in accounts]
    second = alice.post(path, body, idem_key="k1")
    assert first.status_code == second.status_code == 201
    assert second.json() == first.json()
    assert [alice.balance(a) for a in accounts] == balances


@pytest.mark.parametrize("endpoint", ENDPOINTS)
def test_reusing_a_key_for_a_different_request_is_rejected(alice, accounts, requests, endpoint):
    path, body, other = requests[endpoint]
    alice.post(path, body, idem_key="k1")
    balances = [alice.balance(a) for a in accounts]
    resp = alice.post(path, other, idem_key="k1")
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "idempotency_key_reused"
    assert [alice.balance(a) for a in accounts] == balances


def test_same_key_on_a_different_endpoint_is_rejected(alice, requests):
    deposit_path, body, _ = requests["deposit"]
    withdraw_path, _, _ = requests["withdraw"]
    alice.post(deposit_path, body, idem_key="k1")
    assert alice.post(withdraw_path, body, idem_key="k1").status_code == 422


def test_without_a_key_each_request_applies(alice, accounts, requests):
    path, body, _ = requests["deposit"]
    alice.post(path, body)
    alice.post(path, body)
    assert alice.balance(accounts[0]) == 120


def test_keys_are_scoped_per_api_key(alice, bob):
    alice_account, bob_account = alice.account(), bob.account()
    assert (
        alice.post(f"/accounts/{alice_account}/deposit", {"amount": 5}, "shared").status_code == 201
    )
    assert bob.post(f"/accounts/{bob_account}/deposit", {"amount": 7}, "shared").status_code == 201
    assert (alice.balance(alice_account), bob.balance(bob_account)) == (5, 7)


def test_failed_request_does_not_consume_the_key(alice, accounts):
    source, _ = accounts
    path = f"/accounts/{source}/withdraw"
    assert alice.post(path, {"amount": 150}, idem_key="k1").status_code == 422
    alice.post(f"/accounts/{source}/deposit", {"amount": 50})
    assert alice.post(path, {"amount": 150}, idem_key="k1").status_code == 201
    assert alice.balance(source) == 0


@pytest.mark.parametrize("key", ["", "x" * 256])
def test_key_length_is_validated(alice, requests, key):
    path, body, _ = requests["deposit"]
    assert alice.post(path, body, idem_key=key).status_code == 422


def test_concurrent_retries_apply_once(alice, accounts, requests):
    path, body, _ = requests["deposit"]
    responses = []

    def send() -> None:
        responses.append(alice.post(path, body, idem_key="race").json())

    threads = [threading.Thread(target=send) for _ in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert len({r["id"] for r in responses}) == 1
    assert alice.balance(accounts[0]) == 110
