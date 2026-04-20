from decimal import Decimal
from typing import Any

from pydantic import BaseModel, ConfigDict

from domain.payment.enums import Currency
from domain.payment.payment import Payment
from domain.payment.value_objects import IdempotencyKey, Money
from infrastructure.unit_of_work import UnitOfWork


class CreatePaymentData(BaseModel):
    model_config = ConfigDict(frozen=True)

    amount: Decimal
    currency: Currency
    description: str
    metadata: dict[str, Any] | None = None
    webhook_url: str
    idempotency_key: str


class CreatePaymentUseCase:
    def __init__(self, uow: UnitOfWork) -> None:
        self._uow = uow

    async def execute(self, data: CreatePaymentData) -> Payment:
        idempotency_key = IdempotencyKey(value=data.idempotency_key)

        async with self._uow as uow:
            existing = await uow.payment_repository.get_by_idempotency_key(
                idempotency_key
            )
            if existing:
                return existing

            payment = Payment.create(
                money=Money(amount=data.amount, currency=data.currency),
                description=data.description,
                webhook_url=data.webhook_url,
                idempotency_key=idempotency_key,
                metadata=data.metadata,
            )

            await uow.payment_repository.add(payment)
            return payment
