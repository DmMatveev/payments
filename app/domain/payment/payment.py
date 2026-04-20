import uuid
from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel

from domain.payment.exceptions import InvalidPaymentStateError
from domain.payment.value_objects import IdempotencyKey, Money, PaymentStatus


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Payment(BaseModel):
    id: uuid.UUID
    money: Money
    description: str
    webhook_url: str
    idempotency_key: IdempotencyKey
    status: PaymentStatus
    created_at: datetime
    processed_at: datetime | None = None
    metadata: dict[str, Any] | None = None

    @classmethod
    def create(
        cls,
        *,
        money: Money,
        description: str,
        webhook_url: str,
        idempotency_key: IdempotencyKey,
        metadata: dict[str, Any] | None = None,
    ) -> "Payment":
        return cls(
            id=uuid.uuid4(),
            money=money,
            description=description,
            webhook_url=webhook_url,
            idempotency_key=idempotency_key,
            metadata=metadata,
            status=PaymentStatus.PENDING,
            created_at=utcnow(),
        )

    def mark_succeeded(self) -> None:
        self._ensure_pending()
        self.status = PaymentStatus.SUCCEEDED
        self.processed_at = utcnow()

    def mark_failed(self) -> None:
        self._ensure_pending()
        self.status = PaymentStatus.FAILED
        self.processed_at = utcnow()

    def _ensure_pending(self) -> None:
        if self.status is not PaymentStatus.PENDING:
            raise InvalidPaymentStateError(
                f"payment {self.id} is {self.status.value}, cannot transition"
            )
