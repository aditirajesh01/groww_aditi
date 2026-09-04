"""Configuration. Every setting has a working default so the app boots with
no .env, no database, no Redis and no API keys."""

from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    # --- datastores (both have fallbacks, see db.py / kv.py) ---------------
    database_url: str = "sqlite+aiosqlite:///./watchlist.db"
    redis_url: str | None = None

    # --- feed --------------------------------------------------------------
    feed_adapter: str = "simulator"  # "simulator" | "yahoo"

    # --- LLM providers (optional) -----------------------------------------
    gemini_api_key: str | None = None
    openrouter_api_key: str | None = None
    nvidia_api_key: str | None = None

    # "gemini-2.5-flash" is listed by ListModels but 404s for new API keys as
    # of this deployment ("no longer available to new users") -- the *-latest
    # alias is what Google actually routes new keys to.
    gemini_model: str = "gemini-flash-latest"
    # OpenRouter: only ":free" ids are ever requested. The Llama 3.3 free
    # slug this defaulted to has since been withdrawn from the free tier;
    # verified live against openrouter.ai/api/v1/models at deploy time.
    openrouter_model: str = "google/gemma-4-31b-it:free"
    # build.nvidia.com NIM catalog. OpenAI-compatible chat completions.
    nvidia_model: str = "meta/llama-3.1-8b-instruct"

    # Cold-start quota guesses. The router replaces these with whatever the
    # provider's live 429 / quota metadata says — see llm/router.py.
    gemini_rpm: int = 10
    gemini_rpd: int = 500
    openrouter_rpm: int = 20
    openrouter_rpd: int = 50
    # ~40 RPM per NVIDIA's published NIM trial limits; RPD is a proxy for the
    # signup credit pool (roughly 1,000-5,000), not a real daily reset.
    nvidia_rpm: int = 40
    nvidia_rpd: int = 1000

    # --- product knobs -----------------------------------------------------
    attention_cap: int = 5
    min_confirmations: int = 2
    crowd_min_cohort: int = 500
    suspect_disagreement_pct: float = 1.0

    # Sources must be at least this stale before we stop calling them LIVE.
    delayed_after_seconds: int = 120
    stale_after_seconds: int = 900

    # --- simulator ---------------------------------------------------------
    # Fixed epoch keeps a fresh clone byte-reproducible and matches the
    # timestamps in contracts/fixtures/digest.json.
    sim_epoch: str = "2026-09-04T12:45:00Z"
    sim_history_sessions: int = 240
    sim_seed: int = 20260904
    sim_hours_per_session: int = 24

    # Global monotonic sequence starts here purely so demo ids look lived-in.
    seq_origin: int = 184000

    # --- thesis clustering -------------------------------------------------
    thesis_cluster_tau: float = 0.72   # cosine threshold for "same belief"
    thesis_contradiction_tau: float = 0.30
    thesis_daily_cap_per_user: int = 3


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
