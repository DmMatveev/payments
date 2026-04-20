import asyncio
import logging
from typing import Any

import httpx

logger = logging.getLogger(__name__)

# TODO

class HttpWebhookNotifier:
    def __init__(self, max_attempts: int = 3, timeout: float = 10.0) -> None:
        self._max_attempts = max_attempts
        self._timeout = timeout

    async def notify(self, url: str, payload: dict[str, Any]) -> bool:
        for attempt in range(self._max_attempts):
            try:
                async with httpx.AsyncClient() as client:
                    resp = await client.post(url, json=payload, timeout=self._timeout)
                    resp.raise_for_status()
                    return True
            except Exception as exc:
                logger.warning("webhook attempt %d failed: %s", attempt + 1, exc)
                if attempt < self._max_attempts - 1:
                    await asyncio.sleep(2**attempt)
        return False
