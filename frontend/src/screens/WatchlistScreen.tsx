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

const DELTA_TONE: Record<string, string> = {
  up: "text-success-600 dark:text-success-400",
  down: "text-error-600 dark:text-error-400",
  neutral: "text-gray-400",
};
const toneOf = (n: number) => DELTA_TONE[n > 0 ? "up" : n < 0 ? "down" : "neutral"];

export function WatchlistScreen() {
  const store = useStore();
  const reduced = useReducedMotion();
  const entries = store.watchlist?.entries ?? [];

  return (
    <div className="mx-auto flex max-w-5xl flex-col gap-6 px-6 py-8">
      <h1 className="text-2xl font-extrabold tracking-tight text-gray-800 dark:text-white">
        What you watch, and why.
      </h1>

      <section>
        <h2 className="mb-3 text-lg font-bold text-gray-800 dark:text-white">Add a symbol</h2>
        <ThesisComposer onAdd={store.addWatch} busy={store.busy} existing={entries.map((e) => e.symbol)} />
      </section>

      <section>
        <div className="mb-3 flex items-baseline gap-3">
          <h2 className="text-lg font-bold text-gray-800 dark:text-white">Watching {entries.length}</h2>
          <span className="text-xs text-gray-400">
            {entries.filter((e) => e.thesis).length} of {entries.length} have a thesis on record.
          </span>
        </div>

        <ul className="flex flex-col gap-3">
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
          <div className="rounded-2xl border border-dashed border-gray-300 p-8 text-center text-sm text-gray-400 dark:border-gray-700">
            Nothing on the list yet. Add a symbol above — the digest has nothing to check until you do.
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
    entry.position != null ? ((entry.price.last - entry.position.avg_cost) / entry.position.avg_cost) * 100 : null;

  async function saveThesis() {
    await store.patchWatch(entry.symbol, { thesis: draft.trim() || null });
    setEditing(false);
  }

  return (
    <div className="flex flex-col gap-4 rounded-2xl border border-gray-200 bg-white p-5 shadow-sm dark:border-gray-800 dark:bg-gray-900 sm:flex-row sm:items-start sm:justify-between">
      <div className="min-w-0 flex-none sm:w-56">
        <div className="flex flex-wrap items-center gap-2">
          <a href={href({ name: "symbol", symbol: entry.symbol })} className="font-mono text-sm font-bold text-gray-800 hover:text-brand-600 dark:text-white dark:hover:text-brand-400">
            {entry.symbol}
          </a>
          <span className="text-sm text-gray-400">{entry.name}</span>
        </div>
        <div className="mt-1.5"><FreshnessChip provenance={entry.provenance} /></div>
        <div className="mt-1.5 text-xs text-gray-400">
          added {day(entry.added_at)} · cursor at seq {entry.last_seen_seq}
          {entry.position && <> · {entry.position.qty} @ ₹{money(entry.position.avg_cost)}</>}
          {entry.muted_kinds.length > 0 && <> · muted: {entry.muted_kinds.map((k) => SIGNAL_META[k].label).join(", ")}</>}
        </div>
      </div>

      <div className="flex-none text-right sm:w-32">
        <div className="font-mono text-lg font-bold tabular-nums text-gray-800 dark:text-white">
          <span className="mr-0.5 text-sm font-semibold text-gray-400">₹</span>
          <Ticker value={entry.price.last} grouped />
        </div>
        <div className="mt-0.5 flex items-center justify-end gap-1.5 text-xs">
          <span className="text-gray-400">today</span>
          <span className={`font-mono font-semibold ${toneOf(entry.price.change_pct)}`}>
            <Ticker value={entry.price.change_pct} signed suffix="%" />
          </span>
        </div>
        {pnl != null && (
          <div className="mt-0.5 flex items-center justify-end gap-1.5 text-xs">
            <span className="text-gray-400">vs your cost</span>
            <span className={`font-mono font-semibold ${toneOf(pnl)}`}>
              <Ticker value={pnl} signed suffix="%" />
            </span>
          </div>
        )}
      </div>

      <div className="min-w-0 flex-1">
        <span className="text-[11px] font-semibold uppercase tracking-wider text-gray-400">Your thesis</span>
        {editing ? (
          <div className="mt-1.5 flex flex-wrap gap-2">
            <input
              className="min-w-0 flex-1 rounded-lg border border-gray-200 px-3 py-1.5 text-sm outline-none focus:border-brand-500 dark:border-gray-700 dark:bg-gray-800 dark:text-white"
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
            <button type="button" onClick={() => void saveThesis()} className="rounded-lg bg-brand-500 px-3 py-1.5 text-xs font-semibold text-white hover:bg-brand-600">
              Save
            </button>
            <button type="button" onClick={() => setEditing(false)} className="rounded-lg border border-gray-200 px-3 py-1.5 text-xs font-medium text-gray-600 dark:border-gray-700 dark:text-gray-300">
              Cancel
            </button>
          </div>
        ) : entry.thesis ? (
          <>
            <blockquote className="mt-1 text-sm italic text-gray-700 dark:text-gray-200">&ldquo;{entry.thesis}&rdquo;</blockquote>
            {entry.thesis_added_at && <span className="mt-1 block text-xs text-gray-400">written {day(entry.thesis_added_at)}</span>}
          </>
        ) : (
          <p className="mt-1 text-sm text-gray-400">
            No thesis on record. Contradiction checks stay off for {entry.symbol} until there is a belief to check against.
          </p>
        )}
      </div>

      <div className="flex flex-none items-start gap-2">
        {!editing && (
          <button
            type="button"
            onClick={() => {
              setDraft(entry.thesis ?? "");
              setEditing(true);
            }}
            className="rounded-lg border border-gray-200 px-3 py-1.5 text-xs font-medium text-gray-600 hover:bg-gray-50 dark:border-gray-700 dark:text-gray-300 dark:hover:bg-white/5"
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
              className="inline-flex gap-1.5"
            >
              <button
                type="button"
                onClick={() => void store.removeWatch(entry.symbol)}
                className="rounded-lg bg-error-500 px-3 py-1.5 text-xs font-semibold text-white hover:bg-error-600"
              >
                Remove {entry.symbol}
              </button>
              <button type="button" onClick={() => setConfirmRemove(false)} className="rounded-lg border border-gray-200 px-3 py-1.5 text-xs font-medium text-gray-600 dark:border-gray-700 dark:text-gray-300">
                Keep
              </button>
            </motion.span>
          ) : (
            <motion.button
              key="remove"
              type="button"
              initial={reduced ? false : { opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              transition={{ duration: 0.18 }}
              onClick={() => setConfirmRemove(true)}
              className="rounded-lg border border-gray-200 px-3 py-1.5 text-xs font-medium text-gray-600 hover:bg-gray-50 dark:border-gray-700 dark:text-gray-300 dark:hover:bg-white/5"
            >
              Remove
            </motion.button>
          )}
        </AnimatePresence>
      </div>
    </div>
  );
}
