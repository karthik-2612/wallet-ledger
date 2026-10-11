"""Domain objects returned by the service layer."""

from dataclasses import dataclass
from typing import Literal

TransactionType = Literal["deposit", "withdrawal", "transfer_in", "transfer_out"]


@dataclass(frozen=True)
class Account:
    id: str
    currency: str
    balance: int
    created_at: str


@dataclass(frozen=True)
class Transaction:
    id: int
    account_id: str
    type: TransactionType
    amount: int
    balance_after: int
    transfer_id: str | None
    created_at: str


@dataclass(frozen=True)
class Transfer:
    id: str
    from_account_id: str
    to_account_id: str
    amount: int
    currency: str
    created_at: str


@dataclass(frozen=True)
class TransactionPage:
    data: list[Transaction]
    next_before_id: int | None
