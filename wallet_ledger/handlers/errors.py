"""Maps every error to the single JSON error shape: {"error": {"code", "message"}}."""

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException

from wallet_ledger.handlers.schemas import ErrorResponse
from wallet_ledger.service.errors import DomainError, NotFound, Unauthenticated

_STATUS: dict[type[DomainError], int] = {Unauthenticated: 401, NotFound: 404}
DEFAULT_DOMAIN_STATUS = 422

ERROR_RESPONSES: dict[int | str, dict] = {
    status: {"model": ErrorResponse, "description": description}
    for status, description in [
        (401, "Missing or invalid API key"),
        (404, "Account not found or not owned by the caller"),
        (422, "Invalid request or business rule violation"),
    ]
}


def _error(status: int, code: str, message: str, details: list | None = None) -> JSONResponse:
    body = {"code": code, "message": message}
    if details is not None:
        body["details"] = details
    return JSONResponse({"error": body}, status_code=status)


async def _domain_error(_: Request, exc: DomainError) -> JSONResponse:
    status = next(
        (_STATUS[cls] for cls in type(exc).__mro__ if cls in _STATUS), DEFAULT_DOMAIN_STATUS
    )
    return _error(status, exc.code, exc.message)


async def _validation_error(_: Request, exc: RequestValidationError) -> JSONResponse:
    details = [{"loc": list(e["loc"]), "msg": e["msg"], "type": e["type"]} for e in exc.errors()]
    return _error(422, "validation_error", "request validation failed", details)


async def _http_error(_: Request, exc: HTTPException) -> JSONResponse:
    return _error(exc.status_code, "http_error", str(exc.detail))


def install_error_handlers(app: FastAPI) -> None:
    app.add_exception_handler(DomainError, _domain_error)
    app.add_exception_handler(RequestValidationError, _validation_error)
    app.add_exception_handler(HTTPException, _http_error)
