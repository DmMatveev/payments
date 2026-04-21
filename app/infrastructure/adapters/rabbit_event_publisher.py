from faststream.rabbit import RabbitBroker
from pydantic import BaseModel, ConfigDict


class PaymentEventPayload(BaseModel):
    model_config = ConfigDict(frozen=True)

    event_type: str
    payment_id: str


class RabbitEventPublisher:
    def __init__(self, broker: RabbitBroker, queue: str) -> None:
        self._broker = broker
        self._queue = queue

    async def publish(self, payload: PaymentEventPayload) -> None:
        await self._broker.publish(payload.model_dump(), queue=self._queue)
