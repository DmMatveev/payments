import aio_pika
from pydantic import BaseModel, ConfigDict


class PaymentEventPayload(BaseModel):
    model_config = ConfigDict(frozen=True)

    event_type: str
    payment_id: str


class RabbitEventPublisher:
    def __init__(self, channel: aio_pika.abc.AbstractChannel, routing_key: str) -> None:
        self._channel = channel
        self._routing_key = routing_key

    async def publish(self, payload: PaymentEventPayload) -> None:
        await self._channel.default_exchange.publish(
            aio_pika.Message(
                body=payload.model_dump_json().encode(),
                delivery_mode=aio_pika.DeliveryMode.PERSISTENT,
            ),
            routing_key=self._routing_key,
        )
