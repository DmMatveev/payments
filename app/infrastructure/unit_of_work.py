from typing import Self

from sqlalchemy.ext.asyncio import AsyncSession

from infrastructure.adapters.repositories.payment_repository_pg import (
    PostgresPaymentRepository,
)


class UnitOfWork:
    def __init__(
        self,
        session: AsyncSession,
        payment_repository: PostgresPaymentRepository,
    ) -> None:
        self._session = session
        self.payment_repository = payment_repository

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        if exc_type is not None:
            await self.rollback()
        else:
            await self.commit()

    async def commit(self) -> None:
        await self._session.commit()

    async def rollback(self) -> None:
        await self._session.rollback()
