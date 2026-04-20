import uuid
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from domain.payment.enums import Currency, PaymentStatus
from domain.payment.events import DomainEvent
from domain.payment.payment import Payment
from domain.payment.repositories import PaymentRepository
from domain.payment.value_objects import IdempotencyKey, Money
from infrastructure.db.models import OutboxModel, PaymentModel


class PostgresPaymentRepository(PaymentRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, payment: Payment) -> None:
        row = self._to_row(payment)
        self._session.add(row)
        self._enqueue_events(payment)
        await self._session.flush()

    async def get_by_id(self, payment_id: uuid.UUID) -> Payment | None:
        row = await self._get_row_by_id(payment_id)
        return self._to_entity(row) if row else None

    async def get_by_idempotency_key(self, key: IdempotencyKey) -> Payment | None:
        result = await self._session.execute(
            select(PaymentModel).where(PaymentModel.idempotency_key == key.value)
        )
        row = result.scalar_one_or_none()
        return self._to_entity(row) if row else None

    async def update(self, payment: Payment) -> None:
        row = await self._get_row_by_id(payment.id)
        if row is None:
            raise LookupError(f"payment {payment.id} not found")
        row.status = payment.status.value
        row.processed_at = payment.processed_at
        self._enqueue_events(payment)
        await self._session.flush()

    def _enqueue_events(self, payment: Payment) -> None:
        for event in payment.pull_events():
            self._session.add(self._to_outbox(event, payment.id))

    @staticmethod
    def _to_outbox(event: DomainEvent, aggregate_id: uuid.UUID) -> OutboxModel:
        return OutboxModel(
            id=uuid.uuid4(),
            aggregate_id=aggregate_id,
            event_type=event.event_type,
            payload={
                "event_type": event.event_type,
                "payment_id": str(aggregate_id),
            },
        )

    async def _get_row_by_id(self, payment_id: uuid.UUID) -> PaymentModel | None:
        result = await self._session.execute(
            select(PaymentModel).where(PaymentModel.id == payment_id)
        )
        return result.scalar_one_or_none()

    @staticmethod
    def _to_entity(row: PaymentModel) -> Payment:
        amount = (
            row.amount if isinstance(row.amount, Decimal) else Decimal(str(row.amount))
        )
        return Payment(
            id=row.id,
            money=Money(amount=amount, currency=Currency(row.currency)),
            description=row.description,
            webhook_url=row.webhook_url,
            idempotency_key=IdempotencyKey(value=row.idempotency_key),
            metadata=row.metadata_,
            status=PaymentStatus(row.status),
            created_at=row.created_at,
            processed_at=row.processed_at,
        )

    @staticmethod
    def _to_row(payment: Payment) -> PaymentModel:
        return PaymentModel(
            id=payment.id,
            amount=payment.money.amount,
            currency=payment.money.currency.value,
            description=payment.description,
            metadata_=payment.metadata,
            status=payment.status.value,
            idempotency_key=payment.idempotency_key.value,
            webhook_url=payment.webhook_url,
            created_at=payment.created_at,
            processed_at=payment.processed_at,
        )
