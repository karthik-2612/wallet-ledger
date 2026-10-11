from fastapi import APIRouter

from wallet_ledger.handlers.deps import IdempotencyKey, Ledger, Owner
from wallet_ledger.handlers.errors import ERROR_RESPONSES
from wallet_ledger.handlers.schemas import TransferOut, TransferRequest
from wallet_ledger.service.models import Transfer

router = APIRouter(prefix="/transfers", tags=["transfers"], responses=ERROR_RESPONSES)


@router.post("", status_code=201, response_model=TransferOut)
def create_transfer(
    body: TransferRequest, owner: Owner, ledger: Ledger, idem_key: IdempotencyKey = None
) -> Transfer:
    """Move funds from an account the caller owns to any account in the same currency."""
    return ledger.transfer(owner, body.from_account_id, body.to_account_id, body.amount, idem_key)
