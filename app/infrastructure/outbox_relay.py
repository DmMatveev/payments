import asyncio
import logging

import aio_pika
from sqlalchemy import select

from infrastructure.adapters.rabbit_event_publisher import RabbitEventPublisher
from infrastructure.configs import async_session, settings
from infrastructure.db.models import PaymentModel

logger = logging.getLogger(__name__)

PAYMENTS_QUEUE = "payments.new"
DLQ_NAME = "payments.dlq"

QUEUE_ARGUMENTS = {
    "x-dead-letter-exchange": "",
    "x-dead-letter-routing-key": DLQ_NAME,
}
POLL_INTERVAL_SECONDS = 1


async def run_outbox_relay() -> None:
    connection = await aio_pika.connect_robust(settings.rabbitmq_url)
    channel = await connection.channel()

    await channel.declare_queue(PAYMENTS_QUEUE, durable=True, arguments=QUEUE_ARGUMENTS)
    await channel.declare_queue(DLQ_NAME, durable=True)

    publisher = RabbitEventPublisher(channel, routing_key=PAYMENTS_QUEUE)
    logger.info("Outbox relay started")

    try:
        while True:
            if not await _publish_next(publisher):
                await asyncio.sleep(POLL_INTERVAL_SECONDS)
    except asyncio.CancelledError:
        await connection.close()
        raise


async def _publish_next(publisher: RabbitEventPublisher) -> bool:
    async with async_session() as session:
        result = await session.execute(
            select(PaymentModel)
            .where(PaymentModel.pending_event.is_not(None))
            .limit(1)
            .with_for_update(skip_locked=True)
        )
        row = result.scalar_one_or_none()
        if row is None:
            return False

        await publisher.publish(
            {"event_type": row.pending_event, "payment_id": str(row.id)}
        )
        row.pending_event = None
        await session.commit()
        return True
