import { useEffect, useRef, useState } from "react";
import { AnimatePresence, motion, useReducedMotion } from "motion/react";
import { getClient } from "@/api/client";
import type { SymbolRef } from "@/api/types";
import { heightCollapse } from "@/lib/motion";

/**
 * Adding a symbol requires a reason, but a required field feels like a tax and
 * gets filled with junk. So the form is written as one sentence the user
 * finishes — "I'm watching ____ because ____" — with the blanks as underlined
 * gaps rather than boxes. It reads like writing a note to yourself, which is
 * exactly what a thesis is, and what makes contradiction detection possible
 * later: you cannot be shown evidence against a belief you never stated.
 */

const STARTERS = [
  "watching for margin recovery",
  "want it under ₹2,400",
  "hedge for my HDFC position",
  "waiting for the capex cycle to show up in revenue",
  "watching whether the China mix normalises",
  "holding until the promoter pledge unwinds",
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

  return (
    <form className="compose" onSubmit={submit}>
      <div className="compose__sentence">
        <span>I&rsquo;m watching</span>
        <input
          className="compose__blank compose__blank--sym"
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
          className="compose__blank"
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
            <ul className="suggest">
              {results.map((r) => (
                <li key={r.symbol}>
                  <button type="button" onClick={() => setSymbol(r.symbol)}>
                    {r.symbol} <span style={{ opacity: 0.6 }}>{r.name}</span>
                  </button>
                </li>
              ))}
            </ul>
          </motion.div>
        )}
      </AnimatePresence>

      {thesis.trim().length === 0 && (
        <ul className="suggest suggest--prose" aria-label="Thesis starters">
          {STARTERS.slice(0, 4).map((s) => (
            <li key={s}>
              <button
                type="button"
                onClick={() => {
                  setThesis(s);
                  thesisRef.current?.focus();
                }}
              >
                {s}
              </button>
            </li>
          ))}
        </ul>
      )}

      <p className="compose__hint">
        The sentence is the point. A thesis in your own words is what lets us later show you
        evidence that runs <em>against</em> it — without one, we can only tell you that something
        moved. You can leave it blank and add it later.
      </p>

      <div className="compose__foot">
        <button type="submit" className="btn btn--primary" disabled={busy || !symbol.trim()}>
          {busy ? "Adding…" : "Add to watchlist"}
        </button>
        {chosen && <span className="eyebrow">{chosen.name} · {chosen.exchange}</span>}
        {error && <span style={{ color: "var(--neg)", fontSize: "0.8125rem" }}>{error}</span>}
      </div>
    </form>
  );
}
