from typing import Self

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from infrastructure.adapters.repositories.outbox_repository_pg import (
    PostgresOutboxRepository,
)
from infrastructure.adapters.repositories.payment_repository_pg import (
    PostgresPaymentRepository,
)


class UnitOfWork:
    _session: AsyncSession
    payment_repository: PostgresPaymentRepository
    outbox_repository: PostgresOutboxRepository

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def __aenter__(self) -> Self:
        self._session = self._session_factory()
        self.payment_repository = PostgresPaymentRepository(self._session)
        self.outbox_repository = PostgresOutboxRepository(self._session)
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        try:
            if exc_type is not None:
                await self._session.rollback()
            else:
                await self._session.commit()
        finally:
            await self._session.close()
