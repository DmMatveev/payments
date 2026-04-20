import asyncio
import random

from domain.payment.payment import Payment


class RandomPaymentGateway:
    def __init__(
        self,
        success_rate: float = 0.9,
        min_delay: float = 2.0,
        max_delay: float = 5.0,
    ) -> None:
        self._success_rate = success_rate
        self._min_delay = min_delay
        self._max_delay = max_delay

    async def charge(self, payment: Payment) -> bool:
        await asyncio.sleep(random.uniform(self._min_delay, self._max_delay))
        return random.random() < self._success_rate
