import uuid

from domain.payment.exceptions import PaymentNotFoundError
from domain.payment.value_objects import PaymentStatus
from infrastructure.adapters.webhook_notifier_http import HttpWebhookNotifier
from infrastructure.unit_of_work import UnitOfWork


class MarkPaymentFailedUseCase:
    def __init__(self, uow: UnitOfWork, notifier: HttpWebhookNotifier) -> None:
        self._uow = uow
        self._notifier = notifier

    async def execute(self, payment_id: uuid.UUID) -> None:
        async with self._uow as uow:
            payment = await uow.payment_repository.get_by_id(payment_id)
        if payment is None:
            raise PaymentNotFoundError(f"payment {payment_id} not found")

        if payment.status is PaymentStatus.PENDING:
            payment.mark_failed()
            async with self._uow as uow:
                await uow.payment_repository.update(payment)

        if payment.status is not PaymentStatus.FAILED:
            return

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
