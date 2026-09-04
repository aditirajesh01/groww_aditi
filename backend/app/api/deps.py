"""Auth — deliberately trivial (contracts/API.md: "not the point of this
project"). A bearer token maps 1:1 to a user row; the same `device_id` always
returns the same `user_id`, which is how "same account, different device" is
demonstrated without a password anywhere in the system.
"""

from __future__ import annotations

import secrets

from fastapi import Depends, Header, HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from ..db import get_session
from ..models import User


def new_token() -> str:
    return secrets.token_urlsafe(24)


async def get_or_create_user(session: AsyncSession, device_id: str) -> User:
    from ..clock import utc_now

    row = await session.execute(select(User).where(User.device_id == device_id))
    user = row.scalar_one_or_none()
    if user is not None:
        return user

    user = User(
        id=f"usr_{secrets.token_hex(8)}",
        device_id=device_id,
        display_name="",
        token=new_token(),
        attention_cap=5,
        created_at=utc_now(),
    )
    session.add(user)
    try:
        await session.flush()
    except IntegrityError:
        # Two concurrent requests for a brand-new device_id (React firing the
        # session bootstrap more than once before the token lands in
        # localStorage) can both reach the "no existing user" branch. The
        # unique constraint on device_id is the real guard; losing this race
        # just means falling back to whichever row won it.
        await session.rollback()
        row = await session.execute(select(User).where(User.device_id == device_id))
        existing = row.scalar_one_or_none()
        if existing is not None:
            return existing
        raise

    from ..seed import seed_watchlist_for

    await seed_watchlist_for(session, user)
    return user


async def get_current_user(
    authorization: str | None = Header(default=None),
    session: AsyncSession = Depends(get_session),
) -> User:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="missing bearer token")
    token = authorization.split(" ", 1)[1].strip()

    row = await session.execute(select(User).where(User.token == token))
    user = row.scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=401, detail="invalid or expired session")
    return user
