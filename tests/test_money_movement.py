import threading

import pytest

from wallet_ledger.service.errors import InvalidAmount
from wallet_ledger.service.ledger import MAX_AMOUNT, MAX_BALANCE


@pytest.mark.parametrize(
    ("start", "op", "amount", "status", "code", "end"),
    [
        (0, "deposit", 500, 201, None, 500),
        (0, "deposit", MAX_AMOUNT, 201, None, MAX_AMOUNT),
        (500, "withdraw", 200, 201, None, 300),
        (500, "withdraw", 500, 201, None, 0),
        (500, "withdraw", 501, 422, "insufficient_funds", 500),
        (0, "withdraw", 1, 422, "insufficient_funds", 0),
    ],
)
def test_deposit_and_withdraw(alice, start, op, amount, status, code, end):
    account = alice.account(balance=start)
    resp = alice.post(f"/accounts/{account}/{op}", {"amount": amount})
    assert resp.status_code == status
    if code:
        assert resp.json()["error"]["code"] == code
    else:
        txn = resp.json()
        assert txn["type"] == ("deposit" if op == "deposit" else "withdrawal")
        assert txn["amount"] == amount
        assert txn["balance_after"] == end
        assert txn["transfer_id"] is None
    assert alice.balance(account) == end


@pytest.mark.parametrize("op", ["deposit", "withdraw"])
@pytest.mark.parametrize("amount", [0, -1, MAX_AMOUNT + 1, 1.5, 10.0, "10", True, None], ids=repr)
def test_amount_must_be_a_positive_bounded_integer(alice, op, amount):
    account = alice.account(balance=100)
    resp = alice.post(f"/accounts/{account}/{op}", {"amount": amount})
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "validation_error"
    assert alice.balance(account) == 100


@pytest.mark.parametrize("op", ["deposit", "withdraw"])
def test_unknown_account(alice, op):
    resp = alice.post(f"/accounts/acc_missing/{op}", {"amount": 1})
    assert resp.status_code == 404


def test_deposit_beyond_balance_limit_is_rejected(app, alice):
    account = alice.account()
    with app.state.ledger._engine.begin() as conn:
        conn.exec_driver_sql(
            "UPDATE accounts SET balance = ? WHERE id = ?", (MAX_BALANCE - 1, account)
        )
    resp = alice.post(f"/accounts/{account}/deposit", {"amount": 2})
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "balance_limit_exceeded"
    assert alice.balance(account) == MAX_BALANCE - 1


def test_concurrent_withdrawals_never_overdraw(alice):
    account = alice.account(balance=100)
    statuses: list[int] = []

    def withdraw() -> None:
        statuses.append(alice.post(f"/accounts/{account}/withdraw", {"amount": 30}).status_code)

    threads = [threading.Thread(target=withdraw) for _ in range(10)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert sorted(statuses) == [201] * 3 + [422] * 7
    assert alice.balance(account) == 10


@pytest.mark.parametrize("amount", [0, -5, MAX_AMOUNT + 1, 10.0, True], ids=repr)
@pytest.mark.parametrize("op", ["deposit", "withdraw"])
def test_service_validates_amounts_without_relying_on_http(app, alice, op, amount):
    account = alice.account(balance=100)
    owner = app.state.auth.authenticate(alice.key)
    with pytest.raises(InvalidAmount):
        getattr(app.state.ledger, op)(owner, account, amount, None)
    with pytest.raises(InvalidAmount):
        app.state.ledger.transfer(owner, account, "acc_other", amount, None)
    assert alice.balance(account) == 100
