import uuid
from typing import ClassVar

from pydantic import BaseModel, ConfigDict


class DomainEvent(BaseModel):
    model_config = ConfigDict(frozen=True)

    event_type: ClassVar[str]


class PaymentCreated(DomainEvent):
    event_type: ClassVar[str] = "payment.created"
    payment_id: uuid.UUID


class PaymentSucceeded(DomainEvent):
    event_type: ClassVar[str] = "payment.succeeded"
    payment_id: uuid.UUID


class PaymentFailed(DomainEvent):
    event_type: ClassVar[str] = "payment.failed"
    payment_id: uuid.UUID
