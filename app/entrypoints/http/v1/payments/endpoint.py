import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Header

from application.use_cases.create_payment import CreatePaymentData, CreatePaymentUseCase
from application.use_cases.get_payment import GetPaymentUseCase
from domain.payment.payment import Payment
from entrypoints.http.v1.payments.dependencies import get_create_payment_use_case, get_get_payment_use_case
from entrypoints.http.v1.payments.schemas import CreatePaymentRequest, CreatePaymentResponse, PaymentResponse

router = APIRouter(
    prefix="/payments",
    tags=["payments"],
)


def _to_response(payment: Payment) -> PaymentResponse:
    return PaymentResponse(
        id=payment.id,
        amount=payment.money.amount,
        currency=payment.money.currency.value,
        description=payment.description,
        metadata=payment.metadata,
        status=payment.status.value,
        idempotency_key=payment.idempotency_key.value,
        webhook_url=payment.webhook_url,
        created_at=payment.created_at,
        processed_at=payment.processed_at,
    )


@router.post("", status_code=202, response_model=CreatePaymentResponse)
async def create_payment(
    body: CreatePaymentRequest,
    use_case: Annotated[CreatePaymentUseCase, Depends(get_create_payment_use_case)],
    idempotency_key: str = Header(..., alias="Idempotency-Key"),
):
    payment = await use_case.execute(
        CreatePaymentData(
            amount=body.amount,
            currency=body.currency,
            description=body.description,
            metadata=body.metadata,
            webhook_url=body.webhook_url,
            idempotency_key=idempotency_key,
        )
    )
    return CreatePaymentResponse(
        payment_id=payment.id,
        status=payment.status.value,
        created_at=payment.created_at,
    )


@router.get("/{payment_id}", response_model=PaymentResponse)
async def get_payment(
    payment_id: uuid.UUID,
    use_case: Annotated[GetPaymentUseCase, Depends(get_get_payment_use_case)],
):
    payment = await use_case.execute(payment_id)
    return _to_response(payment)
