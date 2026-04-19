import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from domain.payment.payment import Payment
from domain.payment.repositories import PaymentRepository
from domain.payment.value_objects import IdempotencyKey
from infrastructure.db.mappers import (
    apply_payment_to_row,
    payment_to_row,
    row_to_payment,
)
from infrastructure.db.models import PaymentRow


class PostgresPaymentRepository(PaymentRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, payment: Payment) -> None:
        self._session.add(payment_to_row(payment))
        await self._session.flush()

    async def get_by_id(self, payment_id: uuid.UUID) -> Payment | None:
        row = await self._get_row_by_id(payment_id)
        return row_to_payment(row) if row else None

    async def get_by_idempotency_key(self, key: IdempotencyKey) -> Payment | None:
        result = await self._session.execute(
            select(PaymentRow).where(PaymentRow.idempotency_key == key.value)
        )
        row = result.scalar_one_or_none()
        return row_to_payment(row) if row else None

    async def update(self, payment: Payment) -> None:
        row = await self._get_row_by_id(payment.id)
        if row is None:
            raise LookupError(f"payment {payment.id} not found")
        apply_payment_to_row(payment, row)
        await self._session.flush()

    async def _get_row_by_id(self, payment_id: uuid.UUID) -> PaymentRow | None:
        result = await self._session.execute(
            select(PaymentRow).where(PaymentRow.id == payment_id)
        )
        return result.scalar_one_or_none()
