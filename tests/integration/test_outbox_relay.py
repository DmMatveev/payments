import uuid
from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from infrastructure.adapters.rabbit_event_publisher import PaymentEventPayload
from infrastructure.db.models import OutboxModel
from infrastructure.outbox_relay import publish_next_event

# Тест-кейсы:
# 1. Публикует событие и удаляет запись из outbox
# 2. Возвращает False при пустой таблице
# 3. Публикует самое старое событие по created_at


class _SessionCtx:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def __aenter__(self) -> AsyncSession:
        return self._session

    async def __aexit__(self, *args: object) -> None:
        pass


def _mock_session_factory(session: AsyncSession):
    return lambda: _SessionCtx(session)


def _make_outbox(event_type: str = "payment.created") -> OutboxModel:
    payment_id = uuid.uuid4()
    return OutboxModel(
        id=uuid.uuid4(),
        aggregate_id=payment_id,
        event_type=event_type,
        payload={"event_type": event_type, "payment_id": str(payment_id)},
    )


@pytest.mark.asyncio
async def test_case_1(db_session: AsyncSession) -> None:
    """1. Публикует событие и удаляет запись из outbox."""

    msg = _make_outbox("payment.created")
    db_session.add(msg)
    await db_session.flush()

    publisher = AsyncMock()

    with patch(
        "infrastructure.outbox_relay.async_session",
        _mock_session_factory(db_session),
    ):
        result = await publish_next_event(publisher)

    assert result is True
    publisher.publish.assert_awaited_once_with(
        PaymentEventPayload.model_validate(msg.payload)
    )

    remaining = (await db_session.execute(OutboxModel.__table__.select())).all()
    assert remaining == []


@pytest.mark.asyncio
async def test_case_2(db_session: AsyncSession) -> None:
    """2. Возвращает False при пустой таблице."""

    publisher = AsyncMock()

    with patch(
        "infrastructure.outbox_relay.async_session",
        _mock_session_factory(db_session),
    ):
        result = await publish_next_event(publisher)

    assert result is False
    publisher.publish.assert_not_awaited()


@pytest.mark.asyncio
async def test_case_3(db_session: AsyncSession) -> None:
    """3. Публикует самое старое событие по created_at."""

    older = _make_outbox("payment.created")
    newer = _make_outbox("payment.succeeded")
    db_session.add(older)
    await db_session.flush()
    db_session.add(newer)
    await db_session.flush()

    publisher = AsyncMock()

    with patch(
        "infrastructure.outbox_relay.async_session",
        _mock_session_factory(db_session),
    ):
        result = await publish_next_event(publisher)

    assert result is True
    publisher.publish.assert_awaited_once_with(
        PaymentEventPayload.model_validate(older.payload)
    )
