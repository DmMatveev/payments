import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.ports.outbox import OutboxRepository
from app.infrastructure.db.models import OutboxRow


class PostgresOutboxRepository(OutboxRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def enqueue_payment_created(self, payment_id: uuid.UUID) -> None:
        row = OutboxRow(
            payload={"payment_id": str(payment_id), "retry_count": 0},
        )
        self._session.add(row)
        await self._session.flush()

    async def get_unpublished(self, limit: int = 100) -> list[OutboxRow]:
        result = await self._session.execute(
            select(OutboxRow)
            .where(OutboxRow.published.is_(False))
            .limit(limit)
            .with_for_update(skip_locked=True)
        )
        return list(result.scalars().all())

    async def mark_published(self, message: OutboxRow) -> None:
        message.published = True
