from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.ports.unit_of_work import UnitOfWork
from app.application.use_cases.create_payment import CreatePaymentUseCase
from app.application.use_cases.get_payment import GetPaymentUseCase
from app.entrypoints.http.dependencies import get_session
from app.infrastructure.adapters.repositories.outbox_repository_pg import (
    PostgresOutboxRepository,
)
from app.infrastructure.adapters.repositories.payment_repository_pg import (
    PostgresPaymentRepository,
)
from app.infrastructure.unit_of_work import SqlAlchemyUnitOfWork


def get_uow(session: AsyncSession = Depends(get_session)) -> UnitOfWork:
    return SqlAlchemyUnitOfWork(
        session,
        PostgresPaymentRepository(session),
        PostgresOutboxRepository(session),
    )


def get_create_payment_use_case(
    uow: UnitOfWork = Depends(get_uow),
) -> CreatePaymentUseCase:
    return CreatePaymentUseCase(uow)


def get_get_payment_use_case(
    uow: UnitOfWork = Depends(get_uow),
) -> GetPaymentUseCase:
    return GetPaymentUseCase(uow)
