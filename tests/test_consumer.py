import uuid
from decimal import Decimal
from unittest.mock import AsyncMock, patch

import pytest
from faststream.rabbit.testing import TestRabbitBroker
from sqlalchemy.ext.asyncio import AsyncSession

from entrypoints.messaging.worker import broker, payments_queue
from infrastructure.db.models import PaymentModel


class _SessionCtx:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def __aenter__(self) -> AsyncSession:
        return self._session

    async def __aexit__(self, *args: object) -> None:
        pass


def _mock_session_factory(session: AsyncSession):
    return lambda: _SessionCtx(session)


@pytest.fixture
async def payment(db_session: AsyncSession) -> PaymentModel:
    p = PaymentModel(
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


def _publish_body(payment_id: uuid.UUID, retry_count: int = 0) -> dict:
    return {
        "event_type": "payment.created",
        "payment_id": str(payment_id),
        "retry_count": retry_count,
    }


# ── Success ──────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_successful_payment_updates_status(
    db_session: AsyncSession, payment: PaymentModel
) -> None:
    with (
        patch(
            "entrypoints.messaging.worker.async_session",
            _mock_session_factory(db_session),
        ),
        patch("random.random", return_value=0.0),
        patch.object(
            __import__("entrypoints.messaging.worker", fromlist=["notifier"]).notifier,
            "notify",
            new=AsyncMock(return_value=True),
        ),
        patch("asyncio.sleep", new_callable=AsyncMock),
    ):
        async with TestRabbitBroker(broker) as br:
            await br.publish(_publish_body(payment.id), queue=payments_queue)

    await db_session.refresh(payment)
    assert payment.status == "succeeded"
    assert payment.processed_at is not None


@pytest.mark.asyncio
async def test_successful_payment_calls_webhook(
    db_session: AsyncSession, payment: PaymentModel
) -> None:
    worker_mod = __import__("entrypoints.messaging.worker", fromlist=["notifier"])
    mock_notify = AsyncMock(return_value=True)

    with (
        patch(
            "entrypoints.messaging.worker.async_session",
            _mock_session_factory(db_session),
        ),
        patch("random.random", return_value=0.0),
        patch.object(worker_mod.notifier, "notify", new=mock_notify),
        patch("asyncio.sleep", new_callable=AsyncMock),
    ):
        async with TestRabbitBroker(broker) as br:
            await br.publish(_publish_body(payment.id), queue=payments_queue)

    mock_notify.assert_awaited_once()
    url, payload = mock_notify.call_args.args
    assert url == payment.webhook_url
    assert payload["payment_id"] == str(payment.id)
    assert payload["status"] == "succeeded"
    assert payload["amount"] == str(payment.amount)
    assert payload["currency"] == payment.currency


# ── Final failure → DLQ ──────────────────────────────────────────────


@pytest.mark.asyncio
async def test_final_failure_sets_status_failed(
    db_session: AsyncSession, payment: PaymentModel
) -> None:
    worker_mod = __import__("entrypoints.messaging.worker", fromlist=["notifier"])

    with (
        patch(
            "entrypoints.messaging.worker.async_session",
            _mock_session_factory(db_session),
        ),
        patch("random.random", return_value=1.0),
        patch.object(worker_mod.notifier, "notify", new=AsyncMock(return_value=True)),
        patch("asyncio.sleep", new_callable=AsyncMock),
    ):
        async with TestRabbitBroker(broker) as br:
            await br.publish(
                _publish_body(payment.id, retry_count=2), queue=payments_queue
            )

    await db_session.refresh(payment)
    assert payment.status == "failed"
    assert payment.processed_at is not None


@pytest.mark.asyncio
async def test_final_failure_sends_webhook_with_failed_status(
    db_session: AsyncSession, payment: PaymentModel
) -> None:
    worker_mod = __import__("entrypoints.messaging.worker", fromlist=["notifier"])
    mock_notify = AsyncMock(return_value=True)

    with (
        patch(
            "entrypoints.messaging.worker.async_session",
            _mock_session_factory(db_session),
        ),
        patch("random.random", return_value=1.0),
        patch.object(worker_mod.notifier, "notify", new=mock_notify),
        patch("asyncio.sleep", new_callable=AsyncMock),
    ):
        async with TestRabbitBroker(broker) as br:
            await br.publish(
                _publish_body(payment.id, retry_count=2), queue=payments_queue
            )

    mock_notify.assert_awaited_once()
    _, payload = mock_notify.call_args.args
    assert payload["status"] == "failed"


# ── Retry ────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_retry_keeps_status_pending(
    db_session: AsyncSession, payment: PaymentModel
) -> None:
    """On non-final failure, payment stays pending; message is republished and then succeeds."""
    worker_mod = __import__("entrypoints.messaging.worker", fromlist=["notifier"])
    call_count = 0

    def _random():
        nonlocal call_count
        call_count += 1
        return 1.0 if call_count == 1 else 0.0

    with (
        patch(
            "entrypoints.messaging.worker.async_session",
            _mock_session_factory(db_session),
        ),
        patch("random.random", side_effect=_random),
        patch.object(worker_mod.notifier, "notify", new=AsyncMock(return_value=True)),
        patch("asyncio.sleep", new_callable=AsyncMock),
    ):
        async with TestRabbitBroker(broker) as br:
            await br.publish(_publish_body(payment.id), queue=payments_queue)

    await db_session.refresh(payment)
    assert payment.status == "succeeded"


# ── Edge cases ───────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_nonexistent_payment_does_not_crash(
    db_session: AsyncSession,
) -> None:
    worker_mod = __import__("entrypoints.messaging.worker", fromlist=["notifier"])

    with (
        patch(
            "entrypoints.messaging.worker.async_session",
            _mock_session_factory(db_session),
        ),
        patch("random.random", return_value=0.0),
        patch.object(worker_mod.notifier, "notify", new=AsyncMock(return_value=True)),
        patch("asyncio.sleep", new_callable=AsyncMock),
    ):
        async with TestRabbitBroker(broker) as br:
            await br.publish(_publish_body(uuid.uuid4()), queue=payments_queue)
