from dataclasses import dataclass
from decimal import Decimal

from domain.payment.enums import Currency
from domain.payment.exceptions import InvalidIdempotencyKeyError, InvalidMoneyError


@dataclass(frozen=True)
class Money:
    amount: Decimal
    currency: Currency

    def __post_init__(self) -> None:
        if not isinstance(self.amount, Decimal):
            raise InvalidMoneyError("amount must be Decimal")
        if self.amount <= 0:
            raise InvalidMoneyError("amount must be positive")


@dataclass(frozen=True)
class IdempotencyKey:
    value: str

    def __post_init__(self) -> None:
        if not self.value or not self.value.strip():
            raise InvalidIdempotencyKeyError("idempotency key must be non-empty")

    def __str__(self) -> str:
        return self.value
