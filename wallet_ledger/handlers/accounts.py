from typing import Annotated

from fastapi import APIRouter, Query

from wallet_ledger.handlers.deps import IdempotencyKey, Ledger, Owner
from wallet_ledger.handlers.errors import ERROR_RESPONSES
from wallet_ledger.handlers.schemas import (
    AccountOut,
    AmountRequest,
    CreateAccountRequest,
    TransactionOut,
    TransactionPageOut,
)
from wallet_ledger.service.models import Account, Transaction, TransactionPage

router = APIRouter(prefix="/accounts", tags=["accounts"], responses=ERROR_RESPONSES)


@router.post("", status_code=201, response_model=AccountOut)
def create_account(body: CreateAccountRequest, owner: Owner, ledger: Ledger) -> Account:
    return ledger.create_account(owner, body.currency)


@router.get("/{account_id}", response_model=AccountOut)
def get_account(account_id: str, owner: Owner, ledger: Ledger) -> Account:
    return ledger.get_account(owner, account_id)


@router.post("/{account_id}/deposit", status_code=201, response_model=TransactionOut)
def deposit(
    account_id: str,
    body: AmountRequest,
    owner: Owner,
    ledger: Ledger,
    idem_key: IdempotencyKey = None,
) -> Transaction:
    return ledger.deposit(owner, account_id, body.amount, idem_key)


@router.post("/{account_id}/withdraw", status_code=201, response_model=TransactionOut)
def withdraw(
    account_id: str,
    body: AmountRequest,
    owner: Owner,
    ledger: Ledger,
    idem_key: IdempotencyKey = None,
) -> Transaction:
    return ledger.withdraw(owner, account_id, body.amount, idem_key)


@router.get("/{account_id}/transactions", response_model=TransactionPageOut)
def list_transactions(
    account_id: str,
    owner: Owner,
    ledger: Ledger,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    before_id: Annotated[int | None, Query(ge=1, description="Cursor from next_before_id")] = None,
) -> TransactionPage:
    return ledger.list_transactions(owner, account_id, limit, before_id)
