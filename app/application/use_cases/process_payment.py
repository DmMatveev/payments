import asyncio
import logging
import random
import uuid

from pydantic import BaseModel, ConfigDict

from domain.payment.exceptions import PaymentNotFoundError
from domain.payment.payment import Payment
from infrastructure.adapters.webhook_notifier_http import HttpWebhookNotifier
from infrastructure.unit_of_work import UnitOfWork

logger = logging.getLogger(__name__)

GATEWAY_SUCCESS_RATE = 0.9
GATEWAY_MIN_DELAY = 2.0
GATEWAY_MAX_DELAY = 5.0

# TODO


class ProcessPaymentResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    payment: Payment
    succeeded: bool


class ProcessPaymentUseCase:
    def __init__(
        self,
        uow: UnitOfWork,
        notifier: HttpWebhookNotifier,
    ) -> None:
        self._uow = uow
        self._notifier = notifier

    async def execute(
        self, payment_id: uuid.UUID, *, is_final_attempt: bool
    ) -> ProcessPaymentResult:
        async with self._uow as uow:
            payment = await uow.payment_repository.get_by_id(payment_id)
            if payment is None:
                raise PaymentNotFoundError(f"payment {payment_id} not found")

            await asyncio.sleep(random.uniform(GATEWAY_MIN_DELAY, GATEWAY_MAX_DELAY))
            succeeded = random.random() < GATEWAY_SUCCESS_RATE

            if succeeded:
                payment.mark_succeeded()
            elif is_final_attempt:
                payment.mark_failed()
            else:
                return ProcessPaymentResult(payment=payment, succeeded=False)

            await uow.payment_repository.update(payment)

        await self._notifier.notify(
            payment.webhook_url,
            {
                "payment_id": str(payment.id),
                "status": payment.status.value,
                "amount": str(payment.money.amount),
                "currency": payment.money.currency.value,
                "processed_at": payment.processed_at.isoformat()
                if payment.processed_at
                else None,
            },
        )
        return ProcessPaymentResult(payment=payment, succeeded=succeeded)
