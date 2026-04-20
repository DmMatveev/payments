import uuid
from decimal import Decimal
from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from infrastructure.db.models import PaymentModel
from infrastructure.outbox_relay import _publish_next


class _SessionCtx:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def __aenter__(self) -> AsyncSession:
        return self._session

    async def __aexit__(self, *args: object) -> None:
        pass


def _mock_session_factory(session: AsyncSession):
    return lambda: _SessionCtx(session)


def _make_payment(pending_event: str | None = "payment.created") -> PaymentModel:
    return PaymentModel(
        id=uuid.uuid4(),
        amount=Decimal("100.00"),
        currency="USD",
        description="Outbox relay test",
        status="pending",
        idempotency_key=str(uuid.uuid4()),
        webhook_url="https://example.com/hook",
        pending_event=pending_event,
    )


@pytest.mark.asyncio
async def test_publish_next_publishes_pending_event_and_clears_it(
    db_session: AsyncSession,
) -> None:
    payment = _make_payment("payment.created")
    db_session.add(payment)
    await db_session.flush()

    publisher = AsyncMock()

    with patch(
        "infrastructure.outbox_relay.async_session",
        _mock_session_factory(db_session),
    ):
        result = await _publish_next(publisher)

    assert result is True
    publisher.publish.assert_awaited_once_with(
        {"event_type": "payment.created", "payment_id": str(payment.id)}
    )

    await db_session.refresh(payment)
    assert payment.pending_event is None


@pytest.mark.asyncio
async def test_publish_next_returns_false_when_no_pending_events(
    db_session: AsyncSession,
) -> None:
    payment = _make_payment(pending_event=None)
    db_session.add(payment)
    await db_session.flush()

    publisher = AsyncMock()

    with patch(
        "infrastructure.outbox_relay.async_session",
        _mock_session_factory(db_session),
    ):
        result = await _publish_next(publisher)

    assert result is False
    publisher.publish.assert_not_awaited()


@pytest.mark.asyncio
async def test_publish_next_skips_payments_without_pending_event(
    db_session: AsyncSession,
) -> None:
    no_event = _make_payment(pending_event=None)
    with_event = _make_payment("payment.succeeded")
    db_session.add_all([no_event, with_event])
    await db_session.flush()

    publisher = AsyncMock()

    with patch(
        "infrastructure.outbox_relay.async_session",
        _mock_session_factory(db_session),
    ):
        result = await _publish_next(publisher)

    assert result is True
    publisher.publish.assert_awaited_once_with(
        {"event_type": "payment.succeeded", "payment_id": str(with_event.id)}
    )

    await db_session.refresh(no_event)
    await db_session.refresh(with_event)
    assert no_event.pending_event is None
    assert with_event.pending_event is None


@pytest.mark.asyncio
async def test_publish_next_returns_false_when_table_empty(
    db_session: AsyncSession,
) -> None:
    publisher = AsyncMock()

    with patch(
        "infrastructure.outbox_relay.async_session",
        _mock_session_factory(db_session),
    ):
        result = await _publish_next(publisher)

    assert result is False
    publisher.publish.assert_not_awaited()
