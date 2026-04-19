from datetime import datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field

from app.domain.payment.enums import Currency


class CreatePaymentRequest(BaseModel):
    amount: Decimal = Field(gt=0)
    currency: Currency
    description: str
    metadata: dict[str, Any] | None = None
    webhook_url: str


class CreatePaymentResponse(BaseModel):
    payment_id: UUID
    status: str
    created_at: datetime


class PaymentResponse(BaseModel):
    id: UUID
    amount: Decimal
    currency: str
    description: str
    metadata: dict[str, Any] | None
    status: str
    idempotency_key: str
    webhook_url: str
    created_at: datetime
    processed_at: datetime | None
