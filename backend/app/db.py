"""Async SQLAlchemy 2.0 setup with a zero-setup fallback.

Postgres is the deployment target (docker-compose.yml ships one). But a
reviewer should be able to clone, pip install, and run — so if DATABASE_URL is
unset, or is set to a Postgres that is not actually up, we fall back to
aiosqlite and say so loudly in the log rather than refusing to boot.

The schema deliberately carries `user_id` on every user-scoped row even though
we run a single unsharded database. DESIGN.md §5 argues the user tier shards by
`user_id` at 10M users; carrying the shard key now is what makes that a
configuration change later instead of a migration.
"""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from .config import settings

log = logging.getLogger("watchlist.db")

SQLITE_FALLBACK = "sqlite+aiosqlite:///./watchlist.db"


class Base(DeclarativeBase):
    pass


_engine = None
_sessionmaker: async_sessionmaker[AsyncSession] | None = None
_active_url: str = ""


def _make_engine(url: str):
    kwargs: dict = {"echo": False, "future": True}
    if url.startswith("sqlite"):
        # aiosqlite + FastAPI: one connection per session is fine, but we want
        # a shared in-memory DB to survive across sessions during tests.
        kwargs["connect_args"] = {"check_same_thread": False}
    else:
        kwargs["pool_size"] = 10
        kwargs["max_overflow"] = 20
        kwargs["pool_pre_ping"] = True
    return create_async_engine(url, **kwargs)


async def init_db(url: str | None = None) -> str:
    """Connect, creating tables. Returns the URL actually in use."""
    global _engine, _sessionmaker, _active_url

    target = url or settings.database_url
    engine = _make_engine(target)

    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
    except Exception as exc:  # pragma: no cover - exercised only without PG
        if target.startswith("sqlite"):
            raise
        log.warning(
            "DATABASE_URL=%s is not reachable (%s). Falling back to %s. "
            "Run `docker compose up -d` for Postgres, or ignore this — the "
            "app is fully functional on SQLite.",
            target.split("@")[-1],
            type(exc).__name__,
            SQLITE_FALLBACK,
        )
        await engine.dispose()
        target = SQLITE_FALLBACK
        engine = _make_engine(target)
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

    _engine = engine
    _sessionmaker = async_sessionmaker(engine, expire_on_commit=False)
    _active_url = target
    log.info("database ready: %s", _describe(target))
    return target


def _describe(url: str) -> str:
    return "sqlite (zero-setup fallback)" if url.startswith("sqlite") else "postgres"


def active_backend() -> str:
    return _describe(_active_url)


def session_factory() -> async_sessionmaker[AsyncSession]:
    if _sessionmaker is None:
        raise RuntimeError("init_db() has not run")
    return _sessionmaker


async def get_session() -> AsyncIterator[AsyncSession]:
    """FastAPI dependency."""
    async with session_factory()() as session:
        yield session


async def dispose_db() -> None:
    global _engine, _sessionmaker
    if _engine is not None:
        await _engine.dispose()
    _engine = None
    _sessionmaker = None
