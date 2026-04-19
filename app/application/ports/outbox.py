import uuid
from typing import Protocol, runtime_checkable


@runtime_checkable
class OutboxRepository(Protocol):
    async def enqueue_payment_created(self, payment_id: uuid.UUID) -> None: ...
