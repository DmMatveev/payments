from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from app.application.ports.unit_of_work import UnitOfWork
from app.domain.payment.enums import Currency
from app.domain.payment.payment import Payment
from app.domain.payment.value_objects import IdempotencyKey, Money


@dataclass(frozen=True)
class CreatePaymentData:
    amount: Decimal
    currency: Currency
    description: str
    metadata: dict[str, Any] | None
    webhook_url: str
    idempotency_key: str


class CreatePaymentUseCase:
    def __init__(self, uow: UnitOfWork) -> None:
        self._uow = uow

    async def execute(self, data: CreatePaymentData) -> Payment:
        idempotency_key = IdempotencyKey(data.idempotency_key)

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
            await uow.outbox_repository.enqueue_payment_created(payment.id)
            return payment
