import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from infrastructure.db.models import OutboxModel


class PostgresOutboxRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, event_type: str, payment_id: uuid.UUID) -> None:
        self._session.add(
            OutboxModel(
                id=uuid.uuid4(),
                payload={"event_type": event_type, "payment_id": str(payment_id)},
            )
        )
        await self._session.flush()
