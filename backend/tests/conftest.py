from __future__ import annotations

import pytest_asyncio

from app.db import dispose_db, init_db, session_factory


@pytest_asyncio.fixture
async def db_session():
    await init_db("sqlite+aiosqlite:///:memory:")
    async with session_factory()() as session:
        yield session
    await dispose_db()
