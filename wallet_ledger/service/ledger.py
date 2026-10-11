"""Accounts and money movement. Every public method is one database transaction."""

import hashlib
import json
import uuid
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Literal

from sqlalchemy import Connection, Engine, RowMapping

from wallet_ledger.service.errors import (
    BalanceLimitExceeded,
    CurrencyMismatch,
    IdempotencyKeyReused,
    InsufficientFunds,
    InvalidAmount,
    NotFound,
    SameAccountTransfer,
)
from wallet_ledger.service.models import Account, Transaction, TransactionPage, Transfer
from wallet_ledger.store import repo

MAX_AMOUNT = 10**15  # per operation, in minor units
MAX_BALANCE = 10**18  # keeps balance arithmetic well inside SQLite's 64-bit integers
ResourceType = Literal["transaction", "transfer"]


def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="microseconds")


def _new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex}"


def _fingerprint(**request: object) -> str:
    return hashlib.sha256(json.dumps(request, sort_keys=True).encode()).hexdigest()


def _check_amount(amount: int) -> None:
    if type(amount) is not int or not 0 < amount <= MAX_AMOUNT:
        raise InvalidAmount(f"amount must be an integer between 1 and {MAX_AMOUNT}")


def _account(row: RowMapping) -> Account:
    return Account(row["id"], row["currency"], row["balance"], row["created_at"])


def _transaction(row: RowMapping) -> Transaction:
    return Transaction(**row)


def _transfer(row: RowMapping) -> Transfer:
    return Transfer(**row)


class LedgerService:
    def __init__(self, engine: Engine) -> None:
        self._engine = engine

    def create_account(self, owner: int, currency: str) -> Account:
        account = Account(_new_id("acc"), currency, 0, _now())
        with self._engine.begin() as conn:
            repo.insert_account(
                conn,
                id=account.id,
                owner_key_id=owner,
                currency=account.currency,
                balance=account.balance,
                created_at=account.created_at,
            )
        return account

    def get_account(self, owner: int, account_id: str) -> Account:
        with self._engine.begin() as conn:
            return _account(self._owned_account(conn, owner, account_id))

    def deposit(
        self, owner: int, account_id: str, amount: int, idem_key: str | None
    ) -> Transaction:
        return self._post_entry(owner, account_id, amount, "deposit", idem_key)

    def withdraw(
        self, owner: int, account_id: str, amount: int, idem_key: str | None
    ) -> Transaction:
        return self._post_entry(owner, account_id, amount, "withdrawal", idem_key)

    def transfer(
        self, owner: int, from_id: str, to_id: str, amount: int, idem_key: str | None
    ) -> Transfer:
        _check_amount(amount)
        if from_id == to_id:
            raise SameAccountTransfer("cannot transfer to the same account")

        def action(conn: Connection) -> Transfer:
            source = self._owned_account(conn, owner, from_id)
            dest = repo.get_account(conn, to_id)
            if dest is None:
                raise NotFound(f"account {to_id} not found")
            if source["currency"] != dest["currency"]:
                raise CurrencyMismatch("accounts must share a currency")
            source_balance = repo.apply_delta(conn, from_id, -amount, MAX_BALANCE)
            if source_balance is None:
                raise InsufficientFunds(f"account {from_id} has insufficient funds")
            dest_balance = repo.apply_delta(conn, to_id, amount, MAX_BALANCE)
            if dest_balance is None:
                raise BalanceLimitExceeded(f"account {to_id} would exceed {MAX_BALANCE}")

            transfer = Transfer(_new_id("trf"), from_id, to_id, amount, source["currency"], _now())
            repo.insert_transfer(conn, **transfer.__dict__)
            for account_id, kind, balance in (
                (from_id, "transfer_out", source_balance),
                (to_id, "transfer_in", dest_balance),
            ):
                repo.insert_transaction(
                    conn,
                    account_id=account_id,
                    type=kind,
                    amount=amount,
                    balance_after=balance,
                    transfer_id=transfer.id,
                    created_at=transfer.created_at,
                )
            return transfer

        fingerprint = _fingerprint(op="transfer", from_id=from_id, to_id=to_id, amount=amount)
        with self._engine.begin() as conn:
            return self._idempotent(conn, owner, idem_key, fingerprint, "transfer", action)

    def list_transactions(
        self, owner: int, account_id: str, limit: int, before_id: int | None
    ) -> TransactionPage:
        with self._engine.begin() as conn:
            self._owned_account(conn, owner, account_id)
            rows = repo.list_transactions(conn, account_id, limit, before_id)
        data = [_transaction(r) for r in rows]
        next_before_id = data[-1].id if len(data) == limit else None
        return TransactionPage(data, next_before_id)

    def _post_entry(
        self,
        owner: int,
        account_id: str,
        amount: int,
        kind: Literal["deposit", "withdrawal"],
        idem_key: str | None,
    ) -> Transaction:
        _check_amount(amount)

        def action(conn: Connection) -> Transaction:
            self._owned_account(conn, owner, account_id)
            delta = amount if kind == "deposit" else -amount
            balance = repo.apply_delta(conn, account_id, delta, MAX_BALANCE)
            if balance is None and kind == "withdrawal":
                raise InsufficientFunds(f"account {account_id} has insufficient funds")
            if balance is None:
                raise BalanceLimitExceeded(f"account {account_id} would exceed {MAX_BALANCE}")
            created_at = _now()
            txn_id = repo.insert_transaction(
                conn,
                account_id=account_id,
                type=kind,
                amount=amount,
                balance_after=balance,
                transfer_id=None,
                created_at=created_at,
            )
            return Transaction(txn_id, account_id, kind, amount, balance, None, created_at)

        fingerprint = _fingerprint(op=kind, account_id=account_id, amount=amount)
        with self._engine.begin() as conn:
            return self._idempotent(conn, owner, idem_key, fingerprint, "transaction", action)

    def _idempotent[T: Transaction | Transfer](
        self,
        conn: Connection,
        owner: int,
        idem_key: str | None,
        fingerprint: str,
        resource_type: ResourceType,
        action: Callable[[Connection], T],
    ) -> T:
        """Run `action` at most once per (owner, idem_key). The key is recorded in the same
        transaction as the money movement, so either both commit or neither does. Only
        successful results are recorded: a failed request can be retried with the same key."""
        if idem_key is None:
            return action(conn)
        record = repo.get_idempotency_record(conn, owner, idem_key)
        if record is not None:
            if record["fingerprint"] != fingerprint:
                raise IdempotencyKeyReused("Idempotency-Key was already used for another request")
            return self._load(conn, resource_type, record["resource_id"])
        result = action(conn)
        repo.insert_idempotency_record(
            conn,
            api_key_id=owner,
            key=idem_key,
            fingerprint=fingerprint,
            resource_type=resource_type,
            resource_id=str(result.id),
            created_at=_now(),
        )
        return result

    @staticmethod
    def _load(conn: Connection, resource_type: ResourceType, resource_id: str):
        if resource_type == "transfer":
            return _transfer(repo.get_transfer(conn, resource_id))
        return _transaction(repo.get_transaction(conn, int(resource_id)))

    @staticmethod
    def _owned_account(conn: Connection, owner: int, account_id: str) -> RowMapping:
        # Accounts owned by other keys are reported as missing so ids can't be probed.
        row = repo.get_account(conn, account_id)
        if row is None or row["owner_key_id"] != owner:
            raise NotFound(f"account {account_id} not found")
        return row
