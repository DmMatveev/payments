from decimal import Decimal

from pydantic import BaseModel, ConfigDict, field_validator

from domain.payment.enums import Currency
from domain.payment.exceptions import InvalidIdempotencyKeyError, InvalidMoneyError


class Money(BaseModel):
    model_config = ConfigDict(frozen=True)

    amount: Decimal
    currency: Currency

    @field_validator("amount")
    @classmethod
    def _validate_amount(cls, value: Decimal) -> Decimal:
        if value <= 0:
            raise InvalidMoneyError("amount must be positive")
        return value


class IdempotencyKey(BaseModel):
    model_config = ConfigDict(frozen=True)

    value: str

    @field_validator("value")
    @classmethod
    def _validate_value(cls, value: str) -> str:
        if not value or not value.strip():
            raise InvalidIdempotencyKeyError("idempotency key must be non-empty")
        return value

    def __str__(self) -> str:
        return self.value
