from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from domain.payment.exceptions import DuplicatePaymentError, PaymentNotFoundError


async def payment_not_found_handler(_: Request, exc: PaymentNotFoundError) -> JSONResponse:
    return JSONResponse(status_code=404, content={"detail": str(exc)})


async def duplicate_payment_handler(_: Request, exc: DuplicatePaymentError) -> JSONResponse:
    return JSONResponse(status_code=409, content={"detail": "Duplicate idempotency key"})


def register_exception_handlers(app: FastAPI) -> None:
    app.add_exception_handler(PaymentNotFoundError, payment_not_found_handler)
    app.add_exception_handler(DuplicatePaymentError, duplicate_payment_handler)
