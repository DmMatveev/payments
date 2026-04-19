import uuid
from typing import Protocol, runtime_checkable

from app.domain.payment.payment import Payment
from app.domain.payment.value_objects import IdempotencyKey


@runtime_checkable
class PaymentRepository(Protocol):
    async def add(self, payment: Payment) -> None: ...

    async def get_by_id(self, payment_id: uuid.UUID) -> Payment | None: ...

    async def get_by_idempotency_key(self, key: IdempotencyKey) -> Payment | None: ...

    async def update(self, payment: Payment) -> None: ...
