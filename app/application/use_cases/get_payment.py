import uuid

from domain.payment.exceptions import PaymentNotFoundError
from domain.payment.payment import Payment
from infrastructure.adapters.repositories.payment_repository_pg import (
    PostgresPaymentRepository,
)


class GetPaymentUseCase:
    def __init__(self, payment_repository: PostgresPaymentRepository) -> None:
        self._payment_repository = payment_repository

    async def execute(self, payment_id: uuid.UUID) -> Payment:
        payment = await self._payment_repository.get_by_id(payment_id)
        if payment is None:
            raise PaymentNotFoundError(f"Payment {payment_id} not found")
        return payment
