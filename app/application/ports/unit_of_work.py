from abc import ABC, abstractmethod
from typing import Self

from app.application.ports.outbox import OutboxRepository
from app.domain.payment.repositories import PaymentRepository


class UnitOfWork(ABC):
    payment_repository: PaymentRepository
    outbox_repository: OutboxRepository

    @abstractmethod
    async def __aenter__(self) -> Self: ...

    @abstractmethod
    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None: ...

    @abstractmethod
    async def commit(self) -> None: ...

    @abstractmethod
    async def rollback(self) -> None: ...
