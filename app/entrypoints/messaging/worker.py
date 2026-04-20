import asyncio
import logging
import uuid

from faststream import FastStream
from faststream.rabbit import RabbitBroker, RabbitMessage, RabbitQueue

from application.use_cases.process_payment import ProcessPaymentUseCase
from domain.payment.exceptions import InvalidPaymentStateError, PaymentNotFoundError
from infrastructure.adapters.payment_gateway_random import RandomPaymentGateway
from infrastructure.adapters.repositories.payment_repository_pg import (
    PostgresPaymentRepository,
)
from infrastructure.adapters.webhook_notifier_http import HttpWebhookNotifier
from infrastructure.configs import async_session, settings
from infrastructure.unit_of_work import SqlAlchemyUnitOfWork

logger = logging.getLogger(__name__)

MAX_RETRIES = 3
PAYMENTS_QUEUE = "payments.new"
DLQ_NAME = "payments.dlq"

broker = RabbitBroker(settings.rabbitmq_url)
app = FastStream(broker)

payments_queue = RabbitQueue(
    PAYMENTS_QUEUE,
    durable=True,
    arguments={
        "x-dead-letter-exchange": "",
        "x-dead-letter-routing-key": DLQ_NAME,
    },
)
dlq = RabbitQueue(DLQ_NAME, durable=True)

gateway = RandomPaymentGateway()
notifier = HttpWebhookNotifier()


@broker.subscriber(payments_queue)
async def process_payment(body: dict, msg: RabbitMessage) -> None:
    event_type = body.get("event_type", "payment.created")
    if event_type != "payment.created":
        logger.info("Skipping event %s", event_type)
        await msg.ack()
        return

    payment_id = uuid.UUID(body["payment_id"])
    retry_count = body.get("retry_count", 0)
    is_final_attempt = retry_count + 1 >= MAX_RETRIES
    logger.info("Processing payment %s, attempt %d", payment_id, retry_count + 1)

    async with async_session() as session:
        uow = SqlAlchemyUnitOfWork(session, PostgresPaymentRepository(session))
        use_case = ProcessPaymentUseCase(uow, gateway, notifier)
        try:
            result = await use_case.execute(
                payment_id, is_final_attempt=is_final_attempt
            )
        except PaymentNotFoundError:
            logger.error("Payment %s not found", payment_id)
            await msg.ack()
            return
        except InvalidPaymentStateError:
            logger.info("Payment %s already in terminal state", payment_id)
            await msg.ack()
            return

    if result.succeeded:
        await msg.ack()
        logger.info("Payment %s succeeded", payment_id)
        return

    if not is_final_attempt:
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
            {
                "event_type": "payment.created",
                "payment_id": str(payment_id),
                "retry_count": retry_count + 1,
            },
            queue=payments_queue,
        )
        await msg.ack()
    else:
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
