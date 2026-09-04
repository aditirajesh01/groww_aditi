"""The signal cache — Redis when available, an in-process dict when not.

DESIGN.md §4 puts `sig:{symbol}` vectors in Redis so the read path is a
pipelined fetch rather than a recomputation. That property matters for the
architecture story, not for a single-process demo, so the interface is narrow
enough that a dict shim is a genuine drop-in and the code above it never knows
which one it got.

The shim is not a toy: it implements TTLs and the same set operations the
subscription inverted index needs, so `subs:{symbol}` behaves identically.
"""

from __future__ import annotations

import fnmatch
import json
import logging
import time
from typing import Any, Protocol

from .config import settings

log = logging.getLogger("watchlist.kv")


class KV(Protocol):
    backend: str

    async def get(self, key: str) -> Any | None: ...
    async def set(self, key: str, value: Any, ttl: int | None = None) -> None: ...
    async def delete(self, *keys: str) -> None: ...
    async def mget(self, keys: list[str]) -> list[Any | None]: ...
    async def keys(self, pattern: str) -> list[str]: ...
    async def sadd(self, key: str, *members: str) -> None: ...
    async def srem(self, key: str, *members: str) -> None: ...
    async def smembers(self, key: str) -> set[str]: ...
    async def incr(self, key: str, amount: int = 1) -> int: ...
    async def close(self) -> None: ...


class DictKV:
    """Zero-dependency fallback. Same semantics, one process, no durability."""

    backend = "in-process"

    def __init__(self) -> None:
        self._data: dict[str, tuple[Any, float | None]] = {}
        self._sets: dict[str, set[str]] = {}

    def _live(self, key: str) -> bool:
        entry = self._data.get(key)
        if entry is None:
            return False
        _, expires = entry
        if expires is not None and expires < time.time():
            self._data.pop(key, None)
            return False
        return True

    async def get(self, key: str) -> Any | None:
        return self._data[key][0] if self._live(key) else None

    async def set(self, key: str, value: Any, ttl: int | None = None) -> None:
        self._data[key] = (value, time.time() + ttl if ttl else None)

    async def delete(self, *keys: str) -> None:
        for key in keys:
            self._data.pop(key, None)
            self._sets.pop(key, None)

    async def mget(self, keys: list[str]) -> list[Any | None]:
        return [await self.get(k) for k in keys]

    async def keys(self, pattern: str) -> list[str]:
        live = [k for k in list(self._data) if self._live(k)]
        return [k for k in live if fnmatch.fnmatch(k, pattern)]

    async def sadd(self, key: str, *members: str) -> None:
        self._sets.setdefault(key, set()).update(members)

    async def srem(self, key: str, *members: str) -> None:
        self._sets.get(key, set()).difference_update(members)

    async def smembers(self, key: str) -> set[str]:
        return set(self._sets.get(key, set()))

    async def incr(self, key: str, amount: int = 1) -> int:
        current = int(await self.get(key) or 0) + amount
        await self.set(key, current)
        return current

    async def close(self) -> None:
        self._data.clear()
        self._sets.clear()


class RedisKV:
    """redis-py asyncio, with JSON round-tripping so callers pass dicts."""

    backend = "redis"

    def __init__(self, client) -> None:
        self._r = client

    async def get(self, key: str) -> Any | None:
        raw = await self._r.get(key)
        return None if raw is None else json.loads(raw)

    async def set(self, key: str, value: Any, ttl: int | None = None) -> None:
        await self._r.set(key, json.dumps(value, default=str), ex=ttl)

    async def delete(self, *keys: str) -> None:
        if keys:
            await self._r.delete(*keys)

    async def mget(self, keys: list[str]) -> list[Any | None]:
        if not keys:
            return []
        raws = await self._r.mget(keys)
        return [None if r is None else json.loads(r) for r in raws]

    async def keys(self, pattern: str) -> list[str]:
        found: list[str] = []
        async for key in self._r.scan_iter(match=pattern, count=500):
            found.append(key if isinstance(key, str) else key.decode())
        return found

    async def sadd(self, key: str, *members: str) -> None:
        if members:
            await self._r.sadd(key, *members)

    async def srem(self, key: str, *members: str) -> None:
        if members:
            await self._r.srem(key, *members)

    async def smembers(self, key: str) -> set[str]:
        raw = await self._r.smembers(key)
        return {m if isinstance(m, str) else m.decode() for m in raw}

    async def incr(self, key: str, amount: int = 1) -> int:
        return int(await self._r.incrby(key, amount))

    async def close(self) -> None:
        await self._r.aclose()


_kv: KV | None = None


async def init_kv() -> KV:
    """Try Redis; fall back to the dict shim. Never raises."""
    global _kv
    if settings.redis_url:
        try:
            import redis.asyncio as aioredis

            client = aioredis.from_url(
                settings.redis_url, decode_responses=True, socket_connect_timeout=2
            )
            await client.ping()
            _kv = RedisKV(client)
            log.info("cache ready: redis")
            return _kv
        except Exception as exc:  # pragma: no cover - needs a broken Redis
            log.warning(
                "REDIS_URL is set but unreachable (%s). Falling back to the "
                "in-process cache — everything still works.",
                type(exc).__name__,
            )
    _kv = DictKV()
    log.info("cache ready: in-process dict shim (no Redis required)")
    return _kv


def kv() -> KV:
    global _kv
    if _kv is None:
        _kv = DictKV()
    return _kv
