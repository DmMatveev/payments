import uuid

from app.application.ports.unit_of_work import UnitOfWork
from app.domain.payment.exceptions import PaymentNotFoundError
from app.domain.payment.payment import Payment


class GetPaymentUseCase:
    def __init__(self, uow: UnitOfWork) -> None:
        self._uow = uow

    async def execute(self, payment_id: uuid.UUID) -> Payment:
        async with self._uow as uow:
            payment = await uow.payment_repository.get_by_id(payment_id)
            if payment is None:
                raise PaymentNotFoundError(f"Payment {payment_id} not found")
            return payment
