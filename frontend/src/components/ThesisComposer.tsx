import { useEffect, useRef, useState } from "react";
import { AnimatePresence, motion, useReducedMotion } from "motion/react";
import { getClient } from "@/api/client";
import type { SymbolRef } from "@/api/types";
import { heightCollapse } from "@/lib/motion";

const STARTERS = [
  "watching for margin recovery",
  "want it under ₹2,400",
  "hedge for my HDFC position",
  "waiting for the capex cycle to show up in revenue",
];

export function ThesisComposer({
  onAdd,
  busy,
  existing,
}: {
  onAdd: (input: { symbol: string; thesis?: string | null }) => Promise<void>;
  busy: boolean;
  existing: string[];
}) {
  const reduced = useReducedMotion();
  const [symbol, setSymbol] = useState("");
  const [thesis, setThesis] = useState("");
  const [results, setResults] = useState<SymbolRef[]>([]);
  const [error, setError] = useState<string | null>(null);
  const thesisRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    let live = true;
    const q = symbol.trim();
    if (q.length < 1) {
      setResults([]);
      return;
    }
    const handle = window.setTimeout(async () => {
      const api = await getClient();
      const hits = await api.search(q);
      if (live) setResults(hits.filter((h) => !existing.includes(h.symbol)));
    }, 160);
    return () => {
      live = false;
      clearTimeout(handle);
    };
  }, [symbol, existing]);

  const chosen = results.find((r) => r.symbol === symbol.trim().toUpperCase());

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    const sym = symbol.trim().toUpperCase();
    if (!sym) return setError("Name a symbol first.");
    try {
      await onAdd({ symbol: sym, thesis: thesis.trim() || null });
      setSymbol("");
      setThesis("");
      setResults([]);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not add that symbol.");
    }
  }

  const inputCls =
    "min-w-0 flex-1 border-b-2 border-dashed border-gray-300 bg-transparent px-1 pb-1 font-medium text-gray-800 outline-none placeholder:text-gray-300 focus:border-brand-500 dark:border-gray-600 dark:text-white dark:placeholder:text-gray-600";

  return (
    <form onSubmit={submit} className="rounded-2xl border border-gray-200 bg-white p-6 shadow-sm dark:border-gray-800 dark:bg-gray-900">
      <div className="flex flex-wrap items-center gap-2 text-lg font-medium text-gray-700 dark:text-gray-200 sm:text-xl">
        <span>I&rsquo;m watching</span>
        <input
          className={`${inputCls} w-40 font-mono uppercase`}
          value={symbol}
          onChange={(e) => setSymbol(e.target.value)}
          placeholder="TATAMOTORS"
          aria-label="Symbol to watch"
          autoComplete="off"
          spellCheck={false}
        />
        <span>because I&rsquo;m</span>
        <input
          ref={thesisRef}
          className={`${inputCls} basis-64`}
          value={thesis}
          onChange={(e) => setThesis(e.target.value)}
          placeholder="watching for margin recovery"
          aria-label="Why you are watching it, in your own words"
          maxLength={140}
        />
      </div>

      <AnimatePresence initial={false}>
        {results.length > 0 && !chosen && (
          <motion.div key="hits" style={{ overflow: "hidden" }} {...heightCollapse(!!reduced)}>
            <ul className="mt-3 flex flex-wrap gap-1.5">
              {results.map((r) => (
                <li key={r.symbol}>
                  <button
                    type="button"
                    onClick={() => setSymbol(r.symbol)}
                    className="rounded-full border border-gray-200 px-3 py-1 text-xs font-medium text-gray-600 hover:border-brand-300 hover:text-brand-600 dark:border-gray-700 dark:text-gray-300"
                  >
                    {r.symbol} <span className="text-gray-400">{r.name}</span>
                  </button>
                </li>
              ))}
            </ul>
          </motion.div>
        )}
      </AnimatePresence>

      {thesis.trim().length === 0 && (
        <ul className="mt-3 flex flex-wrap gap-1.5" aria-label="Thesis starters">
          {STARTERS.map((s) => (
            <li key={s}>
              <button
                type="button"
                onClick={() => {
                  setThesis(s);
                  thesisRef.current?.focus();
                }}
                className="rounded-full border border-gray-200 px-3 py-1 text-xs font-medium text-gray-500 hover:border-brand-300 hover:text-brand-600 dark:border-gray-700 dark:text-gray-400"
              >
                {s}
              </button>
            </li>
          ))}
        </ul>
      )}

      <p className="mt-4 text-xs leading-relaxed text-gray-400">
        The sentence is the point. A thesis in your own words is what lets us later show you evidence
        that runs <em>against</em> it — without one, we can only tell you that something moved. You can
        leave it blank and add it later.
      </p>

      <div className="mt-4 flex flex-wrap items-center gap-3">
        <button
          type="submit"
          disabled={busy || !symbol.trim()}
          className="rounded-lg bg-brand-500 px-4 py-2.5 text-sm font-semibold text-white shadow-sm hover:bg-brand-600 disabled:opacity-50"
        >
          {busy ? "Adding…" : "Add to watchlist"}
        </button>
        {chosen && <span className="text-xs font-medium text-gray-400">{chosen.name} · {chosen.exchange}</span>}
        {error && <span className="text-xs font-medium text-error-600 dark:text-error-400">{error}</span>}
      </div>
    </form>
  );
}
