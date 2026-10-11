import pytest

from wallet_ledger.service.ledger import MAX_BALANCE


def transfer(caller, source, dest, amount, idem_key=None):
    body = {"from_account_id": source, "to_account_id": dest, "amount": amount}
    return caller.post("/transfers", body, idem_key)


def test_transfer_moves_funds_and_records_both_legs(alice):
    source, dest = alice.account(balance=100), alice.account()
    resp = transfer(alice, source, dest, 40)
    assert resp.status_code == 201
    body = resp.json()
    assert body["id"].startswith("trf_")
    assert body | {"id": None, "created_at": None} == {
        "id": None,
        "from_account_id": source,
        "to_account_id": dest,
        "amount": 40,
        "currency": "USD",
        "created_at": None,
    }
    assert (alice.balance(source), alice.balance(dest)) == (60, 40)

    out = alice.get(f"/accounts/{source}/transactions").json()["data"][0]
    into = alice.get(f"/accounts/{dest}/transactions").json()["data"][0]
    assert (out["type"], out["balance_after"], out["transfer_id"]) == (
        "transfer_out",
        60,
        body["id"],
    )
    assert (into["type"], into["balance_after"], into["transfer_id"]) == (
        "transfer_in",
        40,
        body["id"],
    )


def test_transfer_to_an_account_owned_by_another_key(alice, bob):
    source, dest = alice.account(balance=10), bob.account()
    assert transfer(alice, source, dest, 10).status_code == 201
    assert bob.balance(dest) == 10


@pytest.mark.parametrize(
    ("source_currency", "dest_currency", "start", "amount", "status", "code"),
    [
        ("USD", "USD", 100, 101, 422, "insufficient_funds"),
        ("USD", "EUR", 100, 10, 422, "currency_mismatch"),
    ],
)
def test_rejected_transfers_change_nothing(
    alice, source_currency, dest_currency, start, amount, status, code
):
    source = alice.account(source_currency, balance=start)
    dest = alice.account(dest_currency)
    resp = transfer(alice, source, dest, amount)
    assert resp.status_code == status
    assert resp.json()["error"]["code"] == code
    assert (alice.balance(source), alice.balance(dest)) == (start, 0)
    assert alice.get(f"/accounts/{dest}/transactions").json()["data"] == []


def test_transfer_to_same_account(alice):
    account = alice.account(balance=10)
    resp = transfer(alice, account, account, 5)
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "same_account_transfer"


def test_transfer_to_missing_account(alice):
    source = alice.account(balance=10)
    resp = transfer(alice, source, "acc_missing", 5)
    assert resp.status_code == 404
    assert alice.balance(source) == 10


def test_transfer_is_atomic_when_the_second_leg_fails(app, alice):
    """The debit has already succeeded when the credit is rejected; it must roll back."""
    source, dest = alice.account(balance=10), alice.account()
    with app.state.ledger._engine.begin() as conn:
        conn.exec_driver_sql("UPDATE accounts SET balance = ? WHERE id = ?", (MAX_BALANCE, dest))
    resp = transfer(alice, source, dest, 5)
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "balance_limit_exceeded"
    assert (alice.balance(source), alice.balance(dest)) == (10, MAX_BALANCE)
    assert len(alice.get(f"/accounts/{source}/transactions").json()["data"]) == 1


@pytest.mark.parametrize(
    "payload",
    [
        {"from_account_id": "a", "to_account_id": "b"},
        {"from_account_id": "a", "to_account_id": "b", "amount": 0},
        {"from_account_id": "a", "amount": 1},
        {"from_account_id": "a", "to_account_id": "b", "amount": 1, "memo": "x"},
    ],
)
def test_transfer_rejects_invalid_body(alice, payload):
    assert alice.post("/transfers", payload).status_code == 422
