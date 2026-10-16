"""
GPU Contention Guard.
Ensures exclusive access to the single GPU based on priority levels:
1. LLM (highest)
2. EMBEDDING
3. OCR (lowest)
"""

from __future__ import annotations

import asyncio
import bisect
import logging
import time
from contextlib import asynccontextmanager
from enum import IntEnum

from app.config import get_settings

logger = logging.getLogger("pa.operational.gpu_guard")


class GpuPriority(IntEnum):
    LLM = 1
    EMBEDDING = 2
    OCR = 3


class GpuGuard:
    def __init__(self):
        self._lock = asyncio.Lock()
        self._waiters: list[tuple[int, float, int, asyncio.Event]] = []
        self._settings = get_settings()

    async def acquire(self, priority: GpuPriority, timeout_seconds: float) -> bool:
        """
        Acquire the GPU lock with priority queueing.
        Returns True if acquired, False if timeout was exceeded.
        """
        if not self._lock.locked() and not self._waiters:
            await self._lock.acquire()
            return True

        event = asyncio.Event()
        req_time = time.time()
        
        # entry tuple: (priority, timestamp, id(event), event)
        # Using id(event) as tie-breaker for identical timestamps (rare but possible)
        entry = (priority.value, req_time, id(event), event)
        bisect.insort(self._waiters, entry)

        logger.info(f"GPU Guard: Queued request with priority {priority.name}, timeout {timeout_seconds}s")

        try:
            # Wait for our turn
            await asyncio.wait_for(event.wait(), timeout=timeout_seconds)
            # Acquired permission to lock
            await self._lock.acquire()
            return True
        except asyncio.TimeoutError:
            logger.warning(f"GPU Guard: Timeout for {priority.name} after {timeout_seconds}s. Triggering fallback.")
            try:
                self._waiters.remove(entry)
            except ValueError:
                pass
            return False

    def release(self):
        """Release the GPU lock and notify the next waiter."""
        self._lock.release()
        if self._waiters:
            # Wake up the highest priority waiting task
            _, _, _, event = self._waiters.pop(0)
            event.set()

    @asynccontextmanager
    async def acquire_or_fallback(self, priority: GpuPriority, timeout: float):
        """
        Context manager for GPU acquisition.
        Yields True if acquired, False if fallback is required.
        """
        acquired = await self.acquire(priority, timeout)
        try:
            yield acquired
        finally:
            if acquired:
                self.release()


# Singleton instance
gpu_guard = GpuGuard()
