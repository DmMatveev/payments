import uuid

from domain.payment.exceptions import PaymentNotFoundError
from domain.payment.payment import Payment
from infrastructure.unit_of_work import SqlAlchemyUnitOfWork


class GetPaymentUseCase:
    def __init__(self, uow: SqlAlchemyUnitOfWork) -> None:
        self._uow = uow

    async def execute(self, payment_id: uuid.UUID) -> Payment:
        async with self._uow as uow:
            payment = await uow.payment_repository.get_by_id(payment_id)
            if payment is None:
                raise PaymentNotFoundError(f"Payment {payment_id} not found")
            return payment
