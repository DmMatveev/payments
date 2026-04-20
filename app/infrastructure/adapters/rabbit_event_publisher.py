import json
from typing import Any

import aio_pika


class RabbitEventPublisher:
    def __init__(self, channel: aio_pika.abc.AbstractChannel, routing_key: str) -> None:
        self._channel = channel
        self._routing_key = routing_key

    async def publish(self, payload: dict[str, Any]) -> None:
        await self._channel.default_exchange.publish(
            aio_pika.Message(
                body=json.dumps(payload).encode(),
                delivery_mode=aio_pika.DeliveryMode.PERSISTENT,
            ),
            routing_key=self._routing_key,
        )
