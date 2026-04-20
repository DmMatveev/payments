from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from application.use_cases.create_payment import CreatePaymentUseCase
from application.use_cases.get_payment import GetPaymentUseCase
from entrypoints.http.dependencies import get_session
from infrastructure.adapters.repositories.payment_repository_pg import (
    PostgresPaymentRepository,
)
from infrastructure.unit_of_work import UnitOfWork


def get_uow(session: AsyncSession = Depends(get_session)) -> UnitOfWork:
    return UnitOfWork(session, PostgresPaymentRepository(session))


def get_create_payment_use_case(
    uow: UnitOfWork = Depends(get_uow),
) -> CreatePaymentUseCase:
    return CreatePaymentUseCase(uow)


def get_get_payment_use_case(
    session: AsyncSession = Depends(get_session),
) -> GetPaymentUseCase:
    return GetPaymentUseCase(PostgresPaymentRepository(session))
