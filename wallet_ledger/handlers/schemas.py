"""Request and response bodies."""

from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field

from wallet_ledger.service.ledger import MAX_AMOUNT
from wallet_ledger.service.models import TransactionType

# strict=True rejects 10.0, "10" and true, so an amount is always a real integer.
Amount = Annotated[
    int, Field(strict=True, gt=0, le=MAX_AMOUNT, description="Integer minor units, e.g. cents")
]


class Request(BaseModel):
    model_config = ConfigDict(extra="forbid")


class CreateAccountRequest(Request):
    currency: Annotated[str, Field(pattern=r"^[A-Z]{3}$", examples=["USD"])]


class AmountRequest(Request):
    amount: Amount


class TransferRequest(Request):
    from_account_id: str
    to_account_id: str
    amount: Amount


class AccountOut(BaseModel):
    id: str
    currency: str
    balance: int
    created_at: str


class TransactionOut(BaseModel):
    id: int
    account_id: str
    type: TransactionType
    amount: int
    balance_after: int
    transfer_id: str | None
    created_at: str


class TransferOut(BaseModel):
    id: str
    from_account_id: str
    to_account_id: str
    amount: int
    currency: str
    created_at: str


class TransactionPageOut(BaseModel):
    data: list[TransactionOut]
    next_before_id: int | None = Field(description="Pass as before_id to fetch the next page")


class ErrorDetail(BaseModel):
    code: str
    message: str
    details: list[dict] | None = None


class ErrorResponse(BaseModel):
    error: ErrorDetail
