"""SQLAlchemy 2.0 ORM.

Two things about this schema are load-bearing rather than incidental:

1.  Every user-scoped table carries `user_id` as the leading column of its
    index. At 10k users that is redundant; at 10M it is the shard key, and
    every read-path query is already `WHERE user_id = ?` with no cross-shard
    join. DESIGN.md §5 argues for exactly this — carry the property, decline
    the deployment.

2.  `Event.seq` is the globally monotonic read cursor. It is allocated from a
    single counter row (state/cursor.py) rather than from an autoincrement PK,
    because the cursor has to be monotonic across the *system*, not per-table,
    and because we want to start it at a non-zero origin.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from .db import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    device_id: Mapped[str] = mapped_column(String(120), unique=True, index=True)
    display_name: Mapped[str] = mapped_column(String(80), default="")
    token: Mapped[str] = mapped_column(String(80), index=True)
    attention_cap: Mapped[int] = mapped_column(Integer, default=5)
    created_at: Mapped[datetime] = mapped_column(DateTime)


class Symbol(Base):
    __tablename__ = "symbols"

    symbol: Mapped[str] = mapped_column(String(24), primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    exchange: Mapped[str] = mapped_column(String(8), default="NSE")
    sector: Mapped[str] = mapped_column(String(40), default="")
    yahoo_ticker: Mapped[str] = mapped_column(String(32), default="")


class WatchItem(Base):
    __tablename__ = "watch_items"
    __table_args__ = (
        UniqueConstraint("user_id", "symbol", name="uq_watch_user_symbol"),
        Index("ix_watch_user", "user_id", "symbol"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(String(40), ForeignKey("users.id"))
    symbol: Mapped[str] = mapped_column(String(24))
    thesis: Mapped[str | None] = mapped_column(Text, nullable=True)
    thesis_added_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    # Embedded once at write time so contradiction checking is
    # O(events x distinct beliefs), never O(users). See llm/thesis.py.
    thesis_vector: Mapped[list | None] = mapped_column(JSON, nullable=True)
    thesis_cluster: Mapped[str | None] = mapped_column(String(64), nullable=True)
    qty: Mapped[float | None] = mapped_column(Float, nullable=True)
    avg_cost: Mapped[float | None] = mapped_column(Float, nullable=True)
    muted_kinds: Mapped[list] = mapped_column(JSON, default=list)
    open_count: Mapped[int] = mapped_column(Integer, default=0)
    added_at: Mapped[datetime] = mapped_column(DateTime)


class ReadCursor(Base):
    """Per-user-per-symbol `last_seen_seq`.

    The only write operation is `max()`. That is what makes cross-device merge
    conflict-free and an out-of-order or duplicated ack a no-op.
    """

    __tablename__ = "read_cursors"
    __table_args__ = (
        UniqueConstraint("user_id", "symbol", name="uq_cursor_user_symbol"),
        Index("ix_cursor_user", "user_id", "symbol"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(String(40))
    symbol: Mapped[str] = mapped_column(String(24))
    last_seen_seq: Mapped[int] = mapped_column(Integer, default=0)
    updated_at: Mapped[datetime] = mapped_column(DateTime)


class SeqCounter(Base):
    """Single-row global sequence allocator."""

    __tablename__ = "seq_counter"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    value: Mapped[int] = mapped_column(Integer, default=0)


class Event(Base):
    """A promoted change — one row per symbol-event, shared by every subscriber.

    This is the table that makes the LLM economics work: the summary lives here,
    on the symbol-event, not on a user. Marginal LLM cost per extra subscriber
    is exactly zero because there is no per-user row to fill in.
    """

    __tablename__ = "events"
    __table_args__ = (
        Index("ix_events_symbol_seq", "symbol", "seq"),
        Index("ix_events_seq", "seq"),
    )

    event_id: Mapped[str] = mapped_column(String(40), primary_key=True)
    seq: Mapped[int] = mapped_column(Integer, unique=True)
    symbol: Mapped[str] = mapped_column(String(24))
    name: Mapped[str] = mapped_column(String(120))
    session_index: Mapped[int] = mapped_column(Integer, default=0)

    headline: Mapped[str] = mapped_column(Text)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    summary_state: Mapped[str] = mapped_column(String(16), default="PENDING")
    summary_provider: Mapped[str | None] = mapped_column(String(24), nullable=True)
    content_hash: Mapped[str] = mapped_column(String(64), index=True)

    signals: Mapped[list] = mapped_column(JSON, default=list)
    confirmations: Mapped[int] = mapped_column(Integer, default=0)
    surprise: Mapped[float] = mapped_column(Float, default=0.0)
    is_correction: Mapped[bool] = mapped_column(Boolean, default=False)

    price: Mapped[dict] = mapped_column(JSON, default=dict)
    provenance: Mapped[dict] = mapped_column(JSON, default=dict)
    first_seen: Mapped[datetime] = mapped_column(DateTime)


class Bar(Base):
    """One session of OHLCV, stored raw and adjusted side by side.

    Keeping both is what makes a correction expressible: we can show what we
    printed at the time *and* what it should have been, which is the whole
    point of an append-only correction (DESIGN.md §8).
    """

    __tablename__ = "bars"
    __table_args__ = (
        UniqueConstraint("symbol", "session_index", name="uq_bar_symbol_session"),
        Index("ix_bars_symbol_session", "symbol", "session_index"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    symbol: Mapped[str] = mapped_column(String(24))
    session_index: Mapped[int] = mapped_column(Integer)
    ts: Mapped[datetime] = mapped_column(DateTime)
    raw_close: Mapped[float] = mapped_column(Float)
    adj_close: Mapped[float] = mapped_column(Float)
    volume: Mapped[float] = mapped_column(Float, default=0.0)
    adjusted: Mapped[bool] = mapped_column(Boolean, default=False)


class CorporateAction(Base):
    """Splits, bonuses, dividends.

    `known_at_session` is separate from `ex_session` on purpose. A notice that
    arrives after the ex-date is exactly how an unadjusted print reaches a user,
    and reproducing that is how we demo the correction path honestly.
    """

    __tablename__ = "corporate_actions"
    __table_args__ = (Index("ix_ca_symbol", "symbol", "ex_session"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    symbol: Mapped[str] = mapped_column(String(24))
    kind: Mapped[str] = mapped_column(String(24))  # split | bonus | dividend
    ratio_from: Mapped[float] = mapped_column(Float, default=1.0)
    ratio_to: Mapped[float] = mapped_column(Float, default=1.0)
    cash_amount: Mapped[float] = mapped_column(Float, default=0.0)
    ex_session: Mapped[int] = mapped_column(Integer)
    known_at_session: Mapped[int] = mapped_column(Integer)
    description: Mapped[str] = mapped_column(String(200), default="")
    applied: Mapped[bool] = mapped_column(Boolean, default=False)


class CorporateEvent(Base):
    """Discrete, dated corporate events with a prior — earnings, guidance,
    rating actions, block deals, promoter pledges, index inclusion."""

    __tablename__ = "corporate_events"
    __table_args__ = (Index("ix_ce_symbol_session", "symbol", "session_index"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    symbol: Mapped[str] = mapped_column(String(24))
    session_index: Mapped[int] = mapped_column(Integer)
    kind: Mapped[str] = mapped_column(String(32))
    prior: Mapped[float] = mapped_column(Float, default=1.0)
    headline: Mapped[str] = mapped_column(String(240))
    implied_move_pct: Mapped[float] = mapped_column(Float, default=0.0)
    payload: Mapped[dict] = mapped_column(JSON, default=dict)


class WatchFlow(Base):
    """Aggregate, k-anonymised watchlist adds/removes.

    Only ever written and read in aggregate. There is deliberately no user_id
    column — the privacy property is enforced by the schema, not by a code
    review promise.
    """

    __tablename__ = "watch_flow"
    __table_args__ = (
        UniqueConstraint("symbol", "session_index", name="uq_flow_symbol_session"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    symbol: Mapped[str] = mapped_column(String(24))
    session_index: Mapped[int] = mapped_column(Integer)
    adds: Mapped[int] = mapped_column(Integer, default=0)
    removes: Mapped[int] = mapped_column(Integer, default=0)
    cohort_size: Mapped[int] = mapped_column(Integer, default=0)


class Dismissal(Base):
    """A dismissal teaches a per-user per-signal-kind threshold. Personalisation
    without an ML platform — DESIGN.md §2(4)."""

    __tablename__ = "dismissals"
    __table_args__ = (
        UniqueConstraint("user_id", "signal_kind", name="uq_dismiss_user_kind"),
        Index("ix_dismiss_user", "user_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(String(40))
    signal_kind: Mapped[str] = mapped_column(String(32))
    count: Mapped[int] = mapped_column(Integer, default=0)
    threshold: Mapped[float] = mapped_column(Float, default=0.0)
    updated_at: Mapped[datetime] = mapped_column(DateTime)


class ThesisVerdict(Base):
    """Cached contradiction verdicts, keyed by (event, thesis cluster).

    Keyed by *cluster*, not by user. Many users write semantically the same
    belief; generating once per distinct belief is the single sharpest scaling
    idea in DESIGN.md §7 and this table is where it is cashed in.
    """

    __tablename__ = "thesis_verdicts"
    __table_args__ = (
        UniqueConstraint("event_id", "cluster_id", name="uq_verdict_event_cluster"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    event_id: Mapped[str] = mapped_column(String(40))
    cluster_id: Mapped[str] = mapped_column(String(64))
    symbol: Mapped[str] = mapped_column(String(24))
    exemplar_thesis: Mapped[str] = mapped_column(Text)
    verdict: Mapped[str] = mapped_column(String(16))
    confidence: Mapped[float] = mapped_column(Float, default=0.0)
    rationale: Mapped[str] = mapped_column(Text)
    provider: Mapped[str] = mapped_column(String(24), default="template")
    created_at: Mapped[datetime] = mapped_column(DateTime)


class LLMCacheEntry(Base):
    """Content-hash cache. Identical inputs must never re-call a provider."""

    __tablename__ = "llm_cache"

    key: Mapped[str] = mapped_column(String(80), primary_key=True)
    symbol: Mapped[str] = mapped_column(String(24))
    event_id: Mapped[str] = mapped_column(String(40))
    content_hash: Mapped[str] = mapped_column(String(64))
    text: Mapped[str] = mapped_column(Text)
    provider: Mapped[str] = mapped_column(String(24))
    created_at: Mapped[datetime] = mapped_column(DateTime)


class LLMUsage(Base):
    """Per-provider per-UTC-day call ledger, and the cache hit/miss counters
    that GET /health reports."""

    __tablename__ = "llm_usage"
    __table_args__ = (UniqueConstraint("provider", "day", name="uq_usage_provider_day"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    provider: Mapped[str] = mapped_column(String(24))
    day: Mapped[str] = mapped_column(String(10))
    calls: Mapped[int] = mapped_column(Integer, default=0)
    failures: Mapped[int] = mapped_column(Integer, default=0)
    cache_hits: Mapped[int] = mapped_column(Integer, default=0)
    cache_misses: Mapped[int] = mapped_column(Integer, default=0)
    observed_daily_cap: Mapped[int | None] = mapped_column(Integer, nullable=True)
