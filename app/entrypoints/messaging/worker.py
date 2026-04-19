import asyncio
import logging
import random
from datetime import datetime, timezone

import httpx
from faststream import FastStream
from faststream.rabbit import RabbitBroker, RabbitMessage, RabbitQueue
from sqlalchemy import select

from app.infrastructure.configs.config import settings
from app.infrastructure.configs.session import async_session
from app.infrastructure.db.models import PaymentRow

logger = logging.getLogger(__name__)

MAX_RETRIES = 3

broker = RabbitBroker(settings.rabbitmq_url)
app = FastStream(broker)

payments_queue = RabbitQueue(
    "payments.new",
    durable=True,
    arguments={
        "x-dead-letter-exchange": "",
        "x-dead-letter-routing-key": "payments.dlq",
    },
)
dlq = RabbitQueue("payments.dlq", durable=True)


async def send_webhook(url: str, payload: dict) -> bool:
    for attempt in range(3):
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.post(url, json=payload, timeout=10)
                resp.raise_for_status()
                return True
        except Exception as e:
            logger.warning("Webhook attempt %d failed: %s", attempt + 1, e)
            if attempt < 2:
                await asyncio.sleep(2**attempt)
    return False


@broker.subscriber(payments_queue)
async def process_payment(body: dict, msg: RabbitMessage) -> None:
    payment_id = body["payment_id"]
    retry_count = body.get("retry_count", 0)

    logger.info("Processing payment %s, attempt %d", payment_id, retry_count + 1)

    await asyncio.sleep(random.uniform(2, 5))
    success = random.random() < 0.9

    async with async_session() as session:
        result = await session.execute(
            select(PaymentRow).where(PaymentRow.id == payment_id)
        )
        payment = result.scalar_one_or_none()
        if not payment:
            logger.error("Payment %s not found", payment_id)
            await msg.ack()
            return

        if success:
            payment.status = "succeeded"
            payment.processed_at = datetime.now(timezone.utc)
            await session.commit()

            await send_webhook(
                payment.webhook_url,
                {
                    "payment_id": str(payment.id),
                    "status": "succeeded",
                    "amount": str(payment.amount),
                    "currency": payment.currency,
                    "processed_at": payment.processed_at.isoformat(),
                },
            )
            await msg.ack()
            logger.info("Payment %s succeeded", payment_id)
        else:
            if retry_count + 1 < MAX_RETRIES:
                delay = 2**retry_count
                logger.info(
                    "Payment %s failed, retrying in %ds (attempt %d/%d)",
                    payment_id,
                    delay,
                    retry_count + 2,
                    MAX_RETRIES,
                )
                await asyncio.sleep(delay)
                await broker.publish(
                    {"payment_id": payment_id, "retry_count": retry_count + 1},
                    queue=payments_queue,
                )
                await msg.ack()
            else:
                payment.status = "failed"
                payment.processed_at = datetime.now(timezone.utc)
                await session.commit()

                await send_webhook(
                    payment.webhook_url,
                    {
                        "payment_id": str(payment.id),
                        "status": "failed",
                        "amount": str(payment.amount),
                        "currency": payment.currency,
                        "processed_at": payment.processed_at.isoformat(),
                    },
                )
                await msg.reject(requeue=False)
                logger.warning(
                    "Payment %s failed after %d attempts, moved to DLQ",
                    payment_id,
                    MAX_RETRIES,
                )


@broker.subscriber(dlq)
async def handle_dlq(body: dict, msg: RabbitMessage) -> None:
    logger.error("DLQ received: %s", body)
    await msg.ack()
