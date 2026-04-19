import asyncio
import json
import logging

import aio_pika
from sqlalchemy import select

from infrastructure.configs import async_session, settings
from infrastructure.db.models import OutboxRow

logger = logging.getLogger(__name__)

PAYMENTS_QUEUE = "payments.new"
DLQ_NAME = "payments.dlq"
QUEUE_ARGUMENTS = {
    "x-dead-letter-exchange": "",
    "x-dead-letter-routing-key": DLQ_NAME,
}


async def outbox_worker() -> None:
    connection = await aio_pika.connect_robust(settings.rabbitmq_url)
    channel = await connection.channel()

    await channel.declare_queue(PAYMENTS_QUEUE, durable=True, arguments=QUEUE_ARGUMENTS)
    await channel.declare_queue(DLQ_NAME, durable=True)

    logger.info("Outbox worker started")

    try:
        while True:
            async with async_session() as session:
                result = await session.execute(
                    select(OutboxRow)
                    .where(OutboxRow.published.is_(False))
                    .limit(100)
                    .with_for_update(skip_locked=True)
                )
                messages = result.scalars().all()

                for msg in messages:
                    await channel.default_exchange.publish(
                        aio_pika.Message(
                            body=json.dumps(msg.payload).encode(),
                            delivery_mode=aio_pika.DeliveryMode.PERSISTENT,
                        ),
                        routing_key=PAYMENTS_QUEUE,
                    )
                    msg.published = True

                await session.commit()

            await asyncio.sleep(1)
    except asyncio.CancelledError:
        await connection.close()
        raise
