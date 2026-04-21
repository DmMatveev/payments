import asyncio
import logging
from datetime import datetime, timedelta, timezone

from faststream.rabbit import RabbitBroker, RabbitQueue
from faststream.rabbit.schemas.queue import ClassicQueueArgs
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from infrastructure.adapters.rabbit_event_publisher import (
    PaymentEventPayload,
    RabbitEventPublisher,
)
from infrastructure.configs.config import DLQ_NAME, PAYMENTS_QUEUE, settings
from infrastructure.configs.session import async_session
from infrastructure.db.models import OutboxModel

LOCK_TIMEOUT = timedelta(minutes=1)

logger = logging.getLogger(__name__)

POLL_INTERVAL_SECONDS = 1


async def run_outbox_relay() -> None:
    broker = RabbitBroker(settings.rabbitmq_url)
    await broker.connect()

    queue_args: ClassicQueueArgs = {
        "x-dead-letter-exchange": "",
        "x-dead-letter-routing-key": DLQ_NAME,
    }
    await broker.declare_queue(
        RabbitQueue(PAYMENTS_QUEUE, durable=True, arguments=queue_args)
    )
    await broker.declare_queue(RabbitQueue(DLQ_NAME, durable=True))

    publisher = RabbitEventPublisher(broker, queue=PAYMENTS_QUEUE)
    logger.info("Outbox relay started")

    try:
        while True:
            async with async_session() as session:
                if not await publish_next_event(session, publisher):
                    await asyncio.sleep(POLL_INTERVAL_SECONDS)
    except asyncio.CancelledError:
        await broker.close()
        raise


async def publish_next_event(
    session: AsyncSession, publisher: RabbitEventPublisher
) -> bool:
    cutoff = datetime.now(timezone.utc) - LOCK_TIMEOUT
    result = await session.execute(
        select(OutboxModel)
        .where(
            or_(
                OutboxModel.locked_at.is_(None),
                OutboxModel.locked_at < cutoff,
            )
        )
        .order_by(OutboxModel.created_at)
        .limit(1)
        .with_for_update(skip_locked=True)
    )
    row = result.scalar_one_or_none()
    if row is None:
        return False

    row.locked_at = datetime.now(timezone.utc)
    await session.flush()

    await publisher.publish(PaymentEventPayload.model_validate(row.payload))
    await session.delete(row)
    await session.commit()
    return True
