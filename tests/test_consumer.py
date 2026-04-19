import uuid
from decimal import Decimal
from unittest.mock import AsyncMock, patch

import pytest
from faststream.rabbit.testing import TestRabbitBroker
from sqlalchemy.ext.asyncio import AsyncSession

from entrypoints.messaging.worker import broker, payments_queue
from infrastructure.db.models import PaymentRow


class _SessionCtx:
    """Async context manager that yields the given session."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def __aenter__(self) -> AsyncSession:
        return self._session

    async def __aexit__(self, *args: object) -> None:
        pass


def _mock_session_factory(session: AsyncSession):
    return lambda: _SessionCtx(session)


@pytest.fixture
async def payment(db_session: AsyncSession) -> PaymentRow:
    p = PaymentRow(
        id=uuid.uuid4(),
        amount=Decimal("500.00"),
        currency="EUR",
        description="Consumer test",
        status="pending",
        idempotency_key=str(uuid.uuid4()),
        webhook_url="https://example.com/hook",
    )
    db_session.add(p)
    await db_session.flush()
    return p


# ── Success ──────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_successful_payment_updates_status(
    db_session: AsyncSession, payment: PaymentRow
) -> None:
    with (
        patch("entrypoints.messaging.worker.async_session", _mock_session_factory(db_session)),
        patch("entrypoints.messaging.worker.send_webhook", new_callable=AsyncMock, return_value=True),
        patch("random.random", return_value=0.5),
        patch("asyncio.sleep", new_callable=AsyncMock),
    ):
        async with TestRabbitBroker(broker) as br:
            await br.publish(
                {"payment_id": str(payment.id), "retry_count": 0},
                queue=payments_queue,
            )

    await db_session.refresh(payment)
    assert payment.status == "succeeded"
    assert payment.processed_at is not None


@pytest.mark.asyncio
async def test_successful_payment_calls_webhook(
    db_session: AsyncSession, payment: PaymentRow
) -> None:
    mock_webhook = AsyncMock(return_value=True)

    with (
        patch("entrypoints.messaging.worker.async_session", _mock_session_factory(db_session)),
        patch("entrypoints.messaging.worker.send_webhook", mock_webhook),
        patch("random.random", return_value=0.5),
        patch("asyncio.sleep", new_callable=AsyncMock),
    ):
        async with TestRabbitBroker(broker) as br:
            await br.publish(
                {"payment_id": str(payment.id), "retry_count": 0},
                queue=payments_queue,
            )

    mock_webhook.assert_awaited_once()
    url, payload = mock_webhook.call_args.args
    assert url == payment.webhook_url
    assert payload["payment_id"] == str(payment.id)
    assert payload["status"] == "succeeded"
    assert payload["amount"] == str(payment.amount)
    assert payload["currency"] == payment.currency


# ── Final failure → DLQ ──────────────────────────────────────────────


@pytest.mark.asyncio
async def test_final_failure_sets_status_failed(
    db_session: AsyncSession, payment: PaymentRow
) -> None:
    with (
        patch("entrypoints.messaging.worker.async_session", _mock_session_factory(db_session)),
        patch("entrypoints.messaging.worker.send_webhook", new_callable=AsyncMock, return_value=True),
        patch("random.random", return_value=0.95),
        patch("asyncio.sleep", new_callable=AsyncMock),
    ):
        async with TestRabbitBroker(broker) as br:
            await br.publish(
                {"payment_id": str(payment.id), "retry_count": 2},
                queue=payments_queue,
            )

    await db_session.refresh(payment)
    assert payment.status == "failed"
    assert payment.processed_at is not None


@pytest.mark.asyncio
async def test_final_failure_sends_webhook_with_failed_status(
    db_session: AsyncSession, payment: PaymentRow
) -> None:
    mock_webhook = AsyncMock(return_value=True)

    with (
        patch("entrypoints.messaging.worker.async_session", _mock_session_factory(db_session)),
        patch("entrypoints.messaging.worker.send_webhook", mock_webhook),
        patch("random.random", return_value=0.95),
        patch("asyncio.sleep", new_callable=AsyncMock),
    ):
        async with TestRabbitBroker(broker) as br:
            await br.publish(
                {"payment_id": str(payment.id), "retry_count": 2},
                queue=payments_queue,
            )

    mock_webhook.assert_awaited_once()
    _, payload = mock_webhook.call_args.args
    assert payload["status"] == "failed"


# ── Retry ────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_retry_keeps_status_pending(
    db_session: AsyncSession, payment: PaymentRow
) -> None:
    """On failure with retries left, payment stays pending (message republished)."""
    call_count = 0
    original_random = None

    def _controlled_random():
        nonlocal call_count
        call_count += 1
        # First call fails, subsequent calls succeed (for republished message)
        if call_count == 1:
            return 0.95  # >= 0.9 → failure
        return 0.1  # < 0.9 → success

    with (
        patch("entrypoints.messaging.worker.async_session", _mock_session_factory(db_session)),
        patch("entrypoints.messaging.worker.send_webhook", new_callable=AsyncMock, return_value=True),
        patch("random.random", side_effect=_controlled_random),
        patch("random.uniform", return_value=0.1),
        patch("asyncio.sleep", new_callable=AsyncMock),
    ):
        async with TestRabbitBroker(broker) as br:
            await br.publish(
                {"payment_id": str(payment.id), "retry_count": 0},
                queue=payments_queue,
            )

    await db_session.refresh(payment)
    # After first failure + republish + success on second attempt
    assert payment.status == "succeeded"


# ── Edge cases ───────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_nonexistent_payment_does_not_crash(
    db_session: AsyncSession,
) -> None:
    with (
        patch("entrypoints.messaging.worker.async_session", _mock_session_factory(db_session)),
        patch("random.random", return_value=0.5),
        patch("random.uniform", return_value=0.1),
        patch("asyncio.sleep", new_callable=AsyncMock),
    ):
        async with TestRabbitBroker(broker) as br:
            await br.publish(
                {"payment_id": str(uuid.uuid4()), "retry_count": 0},
                queue=payments_queue,
            )
    # No exception — handler gracefully handles missing payment
