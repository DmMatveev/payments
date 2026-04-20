import uuid
from dataclasses import dataclass
from typing import ClassVar


@dataclass(frozen=True)
class DomainEvent:
    event_type: ClassVar[str]


@dataclass(frozen=True)
class PaymentCreated(DomainEvent):
    event_type: ClassVar[str] = "payment.created"
    payment_id: uuid.UUID


@dataclass(frozen=True)
class PaymentSucceeded(DomainEvent):
    event_type: ClassVar[str] = "payment.succeeded"
    payment_id: uuid.UUID


@dataclass(frozen=True)
class PaymentFailed(DomainEvent):
    event_type: ClassVar[str] = "payment.failed"
    payment_id: uuid.UUID
