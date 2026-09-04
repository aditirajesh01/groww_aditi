import { useEffect, useState } from "react";
import { motion, useReducedMotion } from "motion/react";
import { getClient } from "@/api/client";
import type { SymbolDetail } from "@/api/types";
import { ChangeCard } from "@/components/ChangeCard";
import { FreshnessChip } from "@/components/FreshnessChip";
import { Sparkline } from "@/components/Sparkline";
import { Ticker } from "@/components/Ticker";
import { asOf, day } from "@/lib/format";
import { listVariants, cardVariants } from "@/lib/motion";
import { href } from "@/state/router";
import { useStore } from "@/state/store";

const DELTA_TONE: Record<string, string> = {
  up: "text-success-600 dark:text-success-400",
  down: "text-error-600 dark:text-error-400",
  neutral: "text-gray-400",
};
const toneOf = (n: number) => DELTA_TONE[n > 0 ? "up" : n < 0 ? "down" : "neutral"];

export function SymbolScreen({ symbol }: { symbol: string }) {
  const store = useStore();
  const reduced = useReducedMotion();
  const [detail, setDetail] = useState<SymbolDetail | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let live = true;
    setDetail(null);
    setError(null);
    void (async () => {
      try {
        const api = await getClient();
        const d = await api.getSymbol(symbol);
        if (live) setDetail(d);
      } catch (err) {
        if (live) setError(err instanceof Error ? err.message : "Could not load this symbol.");
      }
    })();
    return () => {
      live = false;
    };
  }, [symbol]);

  const entry = store.watchlist?.entries.find((e) => e.symbol === symbol);

  if (error) {
    return (
      <div className="mx-auto max-w-5xl px-6 py-8">
        <div className="rounded-2xl border border-error-200 bg-error-50 p-6 text-sm text-error-700 dark:border-error-500/30 dark:bg-error-500/10 dark:text-error-400">
          {error}
        </div>
      </div>
    );
  }

  if (!detail) {
    return (
      <div className="mx-auto max-w-5xl px-6 py-8" aria-busy="true">
        <div className="h-10 w-56 animate-pulse rounded-md bg-gray-100 dark:bg-gray-800" />
        <div className="mt-6 h-24 w-full animate-pulse rounded-2xl bg-gray-100 dark:bg-gray-800" />
        <div className="mt-6 h-40 w-full animate-pulse rounded-2xl bg-gray-100 dark:bg-gray-800" />
      </div>
    );
  }

  const p = detail.price;

  return (
    <div className="mx-auto flex max-w-5xl flex-col gap-6 px-6 py-8">
      <header className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <a href={href({ name: "digest" })} className="text-xs font-semibold text-brand-600 hover:underline dark:text-brand-400">
            ← back to digest
          </a>
          <div className="mt-2 flex items-center gap-2">
            <span className="font-mono text-sm font-bold text-gray-500">{detail.symbol}</span>
            <FreshnessChip provenance={detail.provenance} />
          </div>
          <h1 className="mt-1 text-2xl font-extrabold tracking-tight text-gray-800 dark:text-white sm:text-3xl">{detail.name}</h1>
        </div>
        <div className="text-right">
          <div className="font-mono text-2xl font-bold tabular-nums text-gray-800 dark:text-white">
            <span className="mr-0.5 text-lg font-semibold text-gray-400">₹</span>
            <Ticker value={p.last} grouped />
          </div>
          <div className="mt-0.5 flex items-center justify-end gap-1.5 text-xs">
            <span className="text-gray-400">today</span>
            <span className={`font-mono font-semibold ${toneOf(p.change_pct)}`}>
              <Ticker value={p.change_pct} signed suffix="%" />
            </span>
          </div>
          {p.idiosyncratic_pct != null && (
            <div className="mt-0.5 flex items-center justify-end gap-1.5 text-xs">
              <span className="text-gray-400">idiosyncratic</span>
              <span className={`font-mono font-semibold ${toneOf(p.idiosyncratic_pct)}`}>
                <Ticker value={p.idiosyncratic_pct} signed suffix="%" />
              </span>
            </div>
          )}
          <div className="mt-0.5 flex items-center justify-end gap-1.5 text-xs">
            <span className="text-gray-400">volume z</span>
            <span className="font-mono font-semibold text-gray-600 dark:text-gray-300">{p.vol_z.toFixed(1)}σ</span>
          </div>
        </div>
      </header>

      <Sparkline points={detail.sparkline} />

      {detail.thesis && (
        <section>
          <h2 className="mb-2 text-lg font-bold text-gray-800 dark:text-white">Your thesis</h2>
          <motion.blockquote
            initial={reduced ? false : { opacity: 0, y: 6 }}
            animate={{ opacity: 1, y: 0 }}
            transition={reduced ? { duration: 0 } : { duration: 0.45, ease: [0.16, 1, 0.3, 1] }}
            className="max-w-xl text-xl font-medium italic text-gray-700 dark:text-gray-200"
          >
            &ldquo;{detail.thesis}&rdquo;
          </motion.blockquote>
          {entry?.thesis_added_at && <span className="mt-1.5 block text-xs text-gray-400">written {day(entry.thesis_added_at)}</span>}
        </section>
      )}

      <section>
        <div className="mb-3 flex items-baseline gap-3">
          <h2 className="text-lg font-bold text-gray-800 dark:text-white">Timeline</h2>
          <span className="text-xs text-gray-400">
            {detail.timeline.length === 0
              ? "Nothing has cleared the gate for this symbol yet."
              : `${detail.timeline.length} recorded ${detail.timeline.length === 1 ? "change" : "changes"}, newest first. Append-only — corrections are added, never edited over.`}
          </span>
        </div>

        {detail.timeline.length === 0 ? (
          <div className="rounded-2xl border border-dashed border-gray-300 p-8 text-center text-sm text-gray-400 dark:border-gray-700">
            Checked as of {asOf(detail.provenance.as_of)}. Nothing here is an absence of data — it is an
            absence of anything that passed two independent confirming factors.
          </div>
        ) : (
          <motion.ul className="flex flex-col gap-4" variants={listVariants(!!reduced)} initial="hidden" animate="shown">
            {detail.timeline.map((item, i) => (
              <motion.li key={item.event_id} variants={cardVariants(!!reduced)}>
                <ChangeCard item={item} rank={i + 1} readOnly thesisAddedAt={entry?.thesis_added_at} />
              </motion.li>
            ))}
          </motion.ul>
        )}
      </section>
    </div>
  );
}
