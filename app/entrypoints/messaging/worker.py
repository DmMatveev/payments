import asyncio
import logging
import uuid

from faststream import FastStream
from faststream.rabbit import RabbitBroker, RabbitMessage, RabbitQueue
from faststream.rabbit.schemas.queue import ClassicQueueArgs

from application.use_cases.mark_payment_failed import MarkPaymentFailedUseCase
from application.use_cases.process_payment import ProcessPaymentUseCase
from domain.payment.exceptions import InvalidPaymentStateError, PaymentNotFoundError
from infrastructure.adapters.webhook_notifier_http import HttpWebhookNotifier
from infrastructure.configs.config import DLQ_NAME, PAYMENTS_QUEUE, settings
from infrastructure.configs.session import async_session
from infrastructure.unit_of_work import UnitOfWork

logger = logging.getLogger(__name__)

MAX_RETRIES = settings.payment_max_retries

broker = RabbitBroker(settings.rabbitmq_url)
app = FastStream(broker)

dlq_arguments: ClassicQueueArgs = {
    "x-dead-letter-exchange": "",
    "x-dead-letter-routing-key": DLQ_NAME,
}
payments_queue = RabbitQueue(
    PAYMENTS_QUEUE,
    durable=True,
    arguments=dlq_arguments,
)
dlq = RabbitQueue(DLQ_NAME, durable=True)

notifier = HttpWebhookNotifier()


# TODO


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

    uow = UnitOfWork(async_session)
    try:
        result = await ProcessPaymentUseCase(uow, notifier).execute(payment_id)
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
        return

    try:
        await MarkPaymentFailedUseCase(uow, notifier).execute(payment_id)
    except InvalidPaymentStateError:
        logger.info("Payment %s already in terminal state", payment_id)
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
