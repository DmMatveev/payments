from unittest.mock import AsyncMock

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from infrastructure.adapters.rabbit_event_publisher import PaymentEventPayload
from infrastructure.db.models import OutboxModel
from infrastructure.outbox_relay import publish_next_event
from tests.factories import OutboxFactory

# Тест-кейсы:
# 1. Публикует событие и удаляет запись из outbox
# 2. Возвращает False при пустой таблице
# 3. Публикует самое старое событие по created_at


@pytest.mark.asyncio
async def test_case_1(db_session: AsyncSession) -> None:
    """1. Публикует событие и удаляет запись из outbox."""

    msg = await OutboxFactory.create(event_type="payment.created")

    publisher = AsyncMock()
    result = await publish_next_event(db_session, publisher)

    assert result is True
    publisher.publish.assert_awaited_once_with(
        PaymentEventPayload(event_type=msg.event_type, payment_id=str(msg.aggregate_id))
    )

    remaining = (await db_session.execute(OutboxModel.__table__.select())).all()
    assert remaining == []


@pytest.mark.asyncio
async def test_case_2(db_session: AsyncSession) -> None:
    """2. Возвращает False при пустой таблице."""

    publisher = AsyncMock()
    result = await publish_next_event(db_session, publisher)

    assert result is False
    publisher.publish.assert_not_awaited()


@pytest.mark.asyncio
async def test_case_3(db_session: AsyncSession) -> None:
    """3. Публикует самое старое событие по created_at."""

    older = await OutboxFactory.create(event_type="payment.created")
    await OutboxFactory.create(event_type="payment.succeeded")

    publisher = AsyncMock()
    result = await publish_next_event(db_session, publisher)

    assert result is True
    publisher.publish.assert_awaited_once_with(
        PaymentEventPayload(event_type=older.event_type, payment_id=str(older.aggregate_id))
    )
