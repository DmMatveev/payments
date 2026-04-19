from decimal import Decimal

from domain.payment.enums import Currency, PaymentStatus
from domain.payment.payment import Payment
from domain.payment.value_objects import IdempotencyKey, Money
from infrastructure.db.models import PaymentRow


def row_to_payment(row: PaymentRow) -> Payment:
    amount = row.amount if isinstance(row.amount, Decimal) else Decimal(str(row.amount))
    return Payment(
        id=row.id,
        money=Money(amount=amount, currency=Currency(row.currency)),
        description=row.description,
        webhook_url=row.webhook_url,
        idempotency_key=IdempotencyKey(row.idempotency_key),
        metadata=row.metadata_,
        status=PaymentStatus(row.status),
        created_at=row.created_at,
        processed_at=row.processed_at,
    )


def payment_to_row(payment: Payment) -> PaymentRow:
    return PaymentRow(
        id=payment.id,
        amount=payment.money.amount,
        currency=payment.money.currency.value,
        description=payment.description,
        metadata_=payment.metadata,
        status=payment.status.value,
        idempotency_key=payment.idempotency_key.value,
        webhook_url=payment.webhook_url,
        created_at=payment.created_at,
        processed_at=payment.processed_at,
    )


def apply_payment_to_row(payment: Payment, row: PaymentRow) -> None:
    row.status = payment.status.value
    row.processed_at = payment.processed_at
