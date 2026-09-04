import { useState } from "react";
import { AnimatePresence, motion, useReducedMotion } from "motion/react";
import type { WatchEntry } from "@/api/types";
import { FreshnessChip } from "@/components/FreshnessChip";
import { ThesisComposer } from "@/components/ThesisComposer";
import { Ticker } from "@/components/Ticker";
import { day, money } from "@/lib/format";
import { SIGNAL_META } from "@/lib/signals";
import { spring } from "@/lib/motion";
import { href } from "@/state/router";
import { useStore } from "@/state/store";

export function WatchlistScreen() {
  const store = useStore();
  const reduced = useReducedMotion();
  const entries = store.watchlist?.entries ?? [];

  return (
    <div className="wrap">
      <header className="digest-head">
        <h1 className="digest-head__lead" style={{ margin: 0 }}>
          What you watch, and why.
        </h1>
        <p className="digest-head__sub">
          Materiality is personal. Position size, cost basis, how long a symbol has been on the list
          and — above all — the reason you wrote down are what decide whether a 4% move is your
          front page or somebody else&rsquo;s noise.
        </p>
      </header>

      <section className="section">
        <div className="section__head">
          <h2 className="section__title">Add a symbol</h2>
        </div>
        <ThesisComposer
          onAdd={store.addWatch}
          busy={store.busy}
          existing={entries.map((e) => e.symbol)}
        />
      </section>

      <section className="section">
        <div className="section__head">
          <h2 className="section__title">Watching {entries.length}</h2>
          <span className="section__note">
            {entries.filter((e) => e.thesis).length} of {entries.length} have a thesis on record.
          </span>
        </div>

        <ul className="wl">
          <AnimatePresence initial={false} mode="popLayout">
            {entries.map((entry) => (
              <motion.li
                key={entry.symbol}
                layout={!reduced}
                initial={reduced ? false : { opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                exit={reduced ? { opacity: 0 } : { opacity: 0, x: -30, scale: 0.97 }}
                transition={reduced ? { duration: 0 } : spring}
              >
                <WatchRow entry={entry} />
              </motion.li>
            ))}
          </AnimatePresence>
        </ul>

        {entries.length === 0 && (
          <div className="empty-note">
            Nothing on the list yet. Add a symbol above — the digest has nothing to check until you
            do.
          </div>
        )}
      </section>
    </div>
  );
}

function WatchRow({ entry }: { entry: WatchEntry }) {
  const store = useStore();
  const reduced = useReducedMotion();
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState(entry.thesis ?? "");
  const [confirmRemove, setConfirmRemove] = useState(false);

  const pnl =
    entry.position != null
      ? ((entry.price.last - entry.position.avg_cost) / entry.position.avg_cost) * 100
      : null;

  async function saveThesis() {
    await store.patchWatch(entry.symbol, { thesis: draft.trim() || null });
    setEditing(false);
  }

  return (
    <div className="wl__item">
      <div className="wl__id">
        <div className="wl__row1">
          <a className="sym__ticker" href={href({ name: "symbol", symbol: entry.symbol })}>
            {entry.symbol}
          </a>
          <span className="sym__name">{entry.name}</span>
          <FreshnessChip provenance={entry.provenance} />
        </div>
        <span className="eyebrow">
          added {day(entry.added_at)} · cursor at seq {entry.last_seen_seq}
          {entry.position && (
            <>
              {" "}· {entry.position.qty} @ ₹{money(entry.position.avg_cost)}
            </>
          )}
          {entry.muted_kinds.length > 0 && (
            <> · muted: {entry.muted_kinds.map((k) => SIGNAL_META[k].label).join(", ")}</>
          )}
        </span>
      </div>

      <div className="price">
        <div className="price__last">
          <span className="cur">₹</span>
          <Ticker value={entry.price.last} grouped />
        </div>
        <div className="price__delta">
          <span className="price__label">today</span>
          <span className={entry.price.change_pct > 0 ? "up" : entry.price.change_pct < 0 ? "down" : "neutral"}>
            <Ticker value={entry.price.change_pct} signed suffix="%" from={0} />
          </span>
        </div>
        {pnl != null && (
          <div className="price__delta" style={{ marginTop: "0.15rem" }}>
            <span className="price__label">vs your cost</span>
            <span className={pnl > 0 ? "up" : pnl < 0 ? "down" : "neutral"}>
              <Ticker value={pnl} signed suffix="%" from={0} />
            </span>
          </div>
        )}
      </div>

      <div className="wl__thesis">
        <div className="wl__thesis-body">
          <span className="confront__k">Your thesis</span>
          {editing ? (
            <div style={{ display: "flex", gap: "0.5rem", marginTop: "0.4rem", flexWrap: "wrap" }}>
              <input
                className="compose__blank"
                value={draft}
                autoFocus
                maxLength={140}
                onChange={(e) => setDraft(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter") void saveThesis();
                  if (e.key === "Escape") setEditing(false);
                }}
                placeholder="watching for margin recovery"
                aria-label={`Thesis for ${entry.symbol}`}
              />
              <button type="button" className="btn btn--primary btn--sm" onClick={() => void saveThesis()}>
                Save
              </button>
              <button type="button" className="btn btn--ghost btn--sm" onClick={() => setEditing(false)}>
                Cancel
              </button>
            </div>
          ) : entry.thesis ? (
            <>
              <blockquote className="wl__thesis-quote">{entry.thesis}</blockquote>
              {entry.thesis_added_at && (
                <span className="confront__when">written {day(entry.thesis_added_at)}</span>
              )}
            </>
          ) : (
            <p className="wl__thesis-empty">
              No thesis on record. Contradiction checks stay off for {entry.symbol} until there is a
              belief to check against.
            </p>
          )}
        </div>

        <div className="wl__actions">
          {!editing && (
            <button
              type="button"
              className="btn btn--ghost btn--sm"
              onClick={() => {
                setDraft(entry.thesis ?? "");
                setEditing(true);
              }}
            >
              {entry.thesis ? "Edit thesis" : "Write a thesis"}
            </button>
          )}
          <AnimatePresence mode="wait" initial={false}>
            {confirmRemove ? (
              <motion.span
                key="confirm"
                initial={reduced ? false : { opacity: 0, x: 8 }}
                animate={{ opacity: 1, x: 0 }}
                exit={reduced ? { opacity: 0 } : { opacity: 0, x: 8 }}
                transition={{ duration: 0.18 }}
                style={{ display: "inline-flex", gap: "0.35rem" }}
              >
                <button
                  type="button"
                  className="btn btn--danger btn--sm"
                  onClick={() => void store.removeWatch(entry.symbol)}
                >
                  Remove {entry.symbol}
                </button>
                <button
                  type="button"
                  className="btn btn--ghost btn--sm"
                  onClick={() => setConfirmRemove(false)}
                >
                  Keep
                </button>
              </motion.span>
            ) : (
              <motion.button
                key="remove"
                type="button"
                className="btn btn--ghost btn--sm"
                initial={reduced ? false : { opacity: 0 }}
                animate={{ opacity: 1 }}
                exit={{ opacity: 0 }}
                transition={{ duration: 0.18 }}
                onClick={() => setConfirmRemove(true)}
              >
                Remove
              </motion.button>
            )}
          </AnimatePresence>
        </div>
      </div>
    </div>
  );
}
