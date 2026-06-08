"""Rate limiter for API requests."""
import asyncio
from datetime import datetime, timedelta
from typing import Dict, Any


class RateLimiter:
    """Rate limiting for API requests (sliding-window)."""

    def __init__(self, max_per_minute: int = 60):
        self.max_per_minute = max_per_minute
        self.timestamps: list[datetime] = []
        self.queue = asyncio.Queue()

    async def check_limit(self) -> bool:
        now = datetime.now()
        cutoff = now - timedelta(minutes=1)
        self.timestamps = [t for t in self.timestamps if t > cutoff]
        if len(self.timestamps) < self.max_per_minute:
            self.timestamps.append(now)
            return True
        return False

    async def wait_if_limited(self):
        while not await self.check_limit():
            await asyncio.sleep(1)

    async def configure(
        self, max_requests_per_minute: int = 60, enable_queuing: bool = True
    ) -> Dict[str, Any]:
        self.max_per_minute = max_requests_per_minute
        return {
            "configured": True,
            "max_per_minute": max_requests_per_minute,
            "queuing_enabled": enable_queuing,
        }
