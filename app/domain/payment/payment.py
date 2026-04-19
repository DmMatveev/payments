import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from app.domain.payment.enums import PaymentStatus
from app.domain.payment.exceptions import InvalidPaymentStateError
from app.domain.payment.value_objects import IdempotencyKey, Money


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


@dataclass
class Payment:
    id: uuid.UUID
    money: Money
    description: str
    webhook_url: str
    idempotency_key: IdempotencyKey
    status: PaymentStatus
    created_at: datetime
    processed_at: datetime | None = None
    metadata: dict[str, Any] | None = field(default=None)

    @classmethod
    def create(
        cls,
        *,
        money: Money,
        description: str,
        webhook_url: str,
        idempotency_key: IdempotencyKey,
        metadata: dict[str, Any] | None = None,
        payment_id: uuid.UUID | None = None,
        now: datetime | None = None,
    ) -> "Payment":
        return cls(
            id=payment_id or uuid.uuid4(),
            money=money,
            description=description,
            webhook_url=webhook_url,
            idempotency_key=idempotency_key,
            metadata=metadata,
            status=PaymentStatus.PENDING,
            created_at=now or _utcnow(),
        )

    def mark_succeeded(self, *, now: datetime | None = None) -> None:
        self._ensure_pending()
        self.status = PaymentStatus.SUCCEEDED
        self.processed_at = now or _utcnow()

    def mark_failed(self, *, now: datetime | None = None) -> None:
        self._ensure_pending()
        self.status = PaymentStatus.FAILED
        self.processed_at = now or _utcnow()

    def _ensure_pending(self) -> None:
        if self.status is not PaymentStatus.PENDING:
            raise InvalidPaymentStateError(
                f"payment {self.id} is {self.status.value}, cannot transition"
            )
