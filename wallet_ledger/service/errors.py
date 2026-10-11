"""Domain errors. Each carries a stable machine-readable `code`; the handler layer maps
error classes to HTTP status codes."""


class DomainError(Exception):
    code = "domain_error"

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


class Unauthenticated(DomainError):
    code = "unauthenticated"


class NotFound(DomainError):
    code = "not_found"


class InvalidAmount(DomainError):
    code = "invalid_amount"


class InsufficientFunds(DomainError):
    code = "insufficient_funds"


class BalanceLimitExceeded(DomainError):
    code = "balance_limit_exceeded"


class CurrencyMismatch(DomainError):
    code = "currency_mismatch"


class SameAccountTransfer(DomainError):
    code = "same_account_transfer"


class IdempotencyKeyReused(DomainError):
    code = "idempotency_key_reused"
