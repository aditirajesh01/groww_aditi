"""FastAPI app assembly.

Startup does three things, in order: connect the datastores (with the
zero-setup fallbacks db.py/kv.py already implement), hydrate the LLM router's
daily-quota ledger so a restart does not reset the free-tier budget, and run
one ingest cycle at the current sim session so `GET /digest` has something to
show on the very first request — no separate seed step to remember to run.
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .db import dispose_db, init_db, session_factory
from .kv import init_kv
from .llm.router import router as llm_router
from .pipeline import run_cycle

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("watchlist.main")


@asynccontextmanager
async def lifespan(app: FastAPI):
    db_url = await init_db()
    await init_kv()
    log.info("database: %s", db_url)

    llm = llm_router()
    async with session_factory()() as session:
        await llm.hydrate(session)
        try:
            result = await run_cycle(session, llm)
            log.info("startup cycle: %s", result)
        except Exception:
            log.exception("startup ingest cycle failed — the app will still boot; "
                          "GET /digest will show quiet/empty state until a cycle succeeds")

    yield

    await llm.close()
    await dispose_db()


app = FastAPI(title="Delta — Smart Market Watchlist", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

from .api.routes import router as api_router  # noqa: E402

app.include_router(api_router)


@app.get("/")
async def root():
    return {"ok": True, "service": "delta-watchlist", "docs": "/docs"}
