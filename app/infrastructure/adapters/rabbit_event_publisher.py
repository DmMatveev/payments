import json
from typing import TypedDict

import aio_pika


class PaymentEventPayload(TypedDict):
    event_type: str
    payment_id: str


class RabbitEventPublisher:
    def __init__(self, channel: aio_pika.abc.AbstractChannel, routing_key: str) -> None:
        self._channel = channel
        self._routing_key = routing_key

    async def publish(self, payload: PaymentEventPayload) -> None:
        await self._channel.default_exchange.publish(
            aio_pika.Message(
                body=json.dumps(payload).encode(),
                delivery_mode=aio_pika.DeliveryMode.PERSISTENT,
            ),
            routing_key=self._routing_key,
        )
