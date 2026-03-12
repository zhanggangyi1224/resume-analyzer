"""Caching abstraction with Redis-first and in-memory TTL fallback."""

from __future__ import annotations

import asyncio
import json
import time
from dataclasses import dataclass, field

try:
    import redis.asyncio as redis
except ImportError:  # pragma: no cover
    redis = None


@dataclass
class _MemoryRecord:
    """Internal memory cache item with payload and expiration timestamp."""

    payload: str
    expire_at: float


@dataclass
class MemoryTTLCache:
    """Lightweight async-safe in-memory cache used when Redis is unavailable."""

    records: dict[str, _MemoryRecord] = field(default_factory=dict)
    lock: asyncio.Lock = field(default_factory=asyncio.Lock)

    async def get(self, key: str) -> str | None:
        """Return cached payload if key exists and has not expired."""

        async with self.lock:
            record = self.records.get(key)
            if not record:
                return None
            if time.time() > record.expire_at:
                self.records.pop(key, None)
                return None
            return record.payload

    async def set(self, key: str, value: str, ttl_seconds: int) -> None:
        """Store payload with TTL in seconds."""

        expire_at = time.time() + ttl_seconds
        async with self.lock:
            self.records[key] = _MemoryRecord(payload=value, expire_at=expire_at)


class CacheService:
    """JSON cache service with Redis and local-memory fallback strategy."""

    def __init__(self, redis_url: str | None, default_ttl_seconds: int = 3600) -> None:
        self.redis_url = redis_url
        self.default_ttl_seconds = default_ttl_seconds
        self._redis = None
        self._memory = MemoryTTLCache()

    async def _get_redis(self):
        """Create or return Redis client lazily; return None when disabled."""

        if not self.redis_url or redis is None:
            return None
        if self._redis is None:
            self._redis = redis.from_url(self.redis_url, decode_responses=True)
        return self._redis

    async def get_json(self, key: str) -> dict | list | None:
        """Get a JSON-serializable value from cache by key."""

        redis_client = await self._get_redis()
        if redis_client:
            try:
                value = await redis_client.get(key)
                return json.loads(value) if value else None
            except Exception:
                pass

        value = await self._memory.get(key)
        return json.loads(value) if value else None

    async def set_json(
        self,
        key: str,
        value: dict | list,
        ttl_seconds: int | None = None,
    ) -> None:
        """Set a JSON-serializable value with TTL."""

        ttl_seconds = ttl_seconds or self.default_ttl_seconds
        payload = json.dumps(value, ensure_ascii=False)

        redis_client = await self._get_redis()
        if redis_client:
            try:
                await redis_client.set(key, payload, ex=ttl_seconds)
                return
            except Exception:
                pass

        await self._memory.set(key, payload, ttl_seconds=ttl_seconds)
