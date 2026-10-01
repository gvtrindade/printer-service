import asyncio
import logging

import httpx

logger = logging.getLogger(__name__)

MAX_RETRIES = 3
BACKOFF_BASE = 1.0
TIMEOUT = 10.0


async def send_webhook(url: str, payload: dict) -> None:
    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        for attempt in range(1, MAX_RETRIES + 1):
            try:
                resp = await client.post(url, json=payload)
                if resp.is_success:
                    logger.info("webhook delivered to %s (attempt %d)", url, attempt)
                    return
                logger.warning(
                    "webhook %s returned %d (attempt %d/%d)",
                    url, resp.status_code, attempt, MAX_RETRIES,
                )
            except httpx.HTTPError as e:
                logger.warning(
                    "webhook %s failed: %s (attempt %d/%d)",
                    url, e, attempt, MAX_RETRIES,
                )
            if attempt < MAX_RETRIES:
                await asyncio.sleep(BACKOFF_BASE * 2 ** (attempt - 1))

    logger.error("webhook %s failed after %d attempts — payload dropped", url, MAX_RETRIES)
