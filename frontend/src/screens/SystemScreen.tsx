import { motion, useReducedMotion } from "motion/react";
import { asOf, FRESHNESS_NOTE } from "@/lib/format";
import { useStore } from "@/state/store";

const STATE_NOTE: Record<string, string> = {
  OK: "Serving normally.",
  RATE_LIMITED: "Throttled. Summaries fall back to the next provider or to the deterministic headline.",
  QUOTA_EXHAUSTED: "Daily cap reached. Cards render from headline + signals only.",
  CIRCUIT_OPEN: "Breaker open after repeated failures. Not being called.",
};

/**
 * Degradation made visible. If the language layer is down, the user should be
 * able to see that it is down rather than wonder why the writing got worse.
 */
export function SystemScreen() {
  const store = useStore();
  const reduced = useReducedMotion();
  const health = store.health;

  return (
    <div className="wrap">
      <header className="digest-head">
        <h1 className="digest-head__lead" style={{ margin: 0 }}>
          What the system knows about itself.
        </h1>
        <p className="digest-head__sub">
          Every number in this product carries provenance and an as-of stamp. So does the product.
        </p>
      </header>

      <section className="section">
        <div className="grid-2">
          <motion.div
            className="panel"
            initial={reduced ? false : { opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            transition={reduced ? { duration: 0 } : { duration: 0.4 }}
          >
            <h2 className="panel__title">Market data</h2>
            {health ? (
              <dl className="kv">
                <dt>Source</dt>
                <dd>{health.market_data.source}</dd>
                <dt>Freshness</dt>
                <dd>{health.market_data.freshness}</dd>
                <dt>As of</dt>
                <dd>{asOf(health.market_data.as_of)}</dd>
                <dt>Summary cache hit rate (24h)</dt>
                <dd>{(health.cache_hit_rate_24h * 100).toFixed(0)}%</dd>
              </dl>
            ) : (
              <div className="skel" style={{ height: "6rem" }} />
            )}
            {health && (
              <p className="section__note" style={{ marginTop: "var(--space-4)" }}>
                {FRESHNESS_NOTE[health.market_data.freshness]}
              </p>
            )}
          </motion.div>

          <motion.div
            className="panel"
            initial={reduced ? false : { opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            transition={reduced ? { duration: 0 } : { duration: 0.4, delay: 0.06 }}
          >
            <h2 className="panel__title">Language layer</h2>
            {health?.llm_providers.map((p) => {
              const ratio = p.daily_cap > 0 ? Math.min(1, p.used_today / p.daily_cap) : 0;
              return (
                <div key={p.name} style={{ marginBottom: "var(--space-4)" }}>
                  <div className="kv">
                    <dt style={{ fontFamily: "var(--font-mono)", fontSize: "0.75rem" }}>{p.name}</dt>
                    <dd
                      style={{
                        color:
                          p.state === "OK"
                            ? "var(--pos)"
                            : p.state === "CIRCUIT_OPEN"
                              ? "var(--neg)"
                              : "var(--brass)",
                      }}
                    >
                      {p.state}
                    </dd>
                  </div>
                  <div className="quota" data-state={p.state}>
                    <motion.i
                      initial={reduced ? false : { width: 0 }}
                      animate={{ width: `${ratio * 100}%` }}
                      transition={reduced ? { duration: 0 } : { duration: 0.7, ease: [0.16, 1, 0.3, 1] }}
                    />
                  </div>
                  <span className="eyebrow">
                    {p.daily_cap > 0 ? `${p.used_today} / ${p.daily_cap} today` : `${p.used_today} today · no cap`}
                    {p.resets_at && ` · resets ${asOf(p.resets_at)}`}
                  </span>
                  <p className="section__note" style={{ marginTop: "0.3rem" }}>
                    {STATE_NOTE[p.state]}
                  </p>
                </div>
              );
            })}
          </motion.div>
        </div>

        <div className="panel" style={{ marginTop: "var(--space-4)" }}>
          <h2 className="panel__title">Client</h2>
          <dl className="kv">
            <dt>Data source</dt>
            <dd>{store.mode === "fixtures" ? "contracts/fixtures/*.json" : "live API"}</dd>
            <dt>Attention budget</dt>
            <dd>
              {store.budget.shown} / {store.budget.cap}
            </dd>
            <dt>Suppressed this digest</dt>
            <dd>{store.budget.suppressed}</dd>
            <dt>Unread in view</dt>
            <dd>{store.unread}</dd>
          </dl>
          {store.mode === "fixtures" && (
            <div style={{ marginTop: "var(--space-4)", display: "flex", gap: "0.5rem", flexWrap: "wrap" }}>
              <button className="btn btn--sm" onClick={() => void store.advanceSim(6)} disabled={store.busy}>
                Advance replay clock 6h
              </button>
              <button className="btn btn--sm btn--ghost" onClick={() => void store.refresh()} disabled={store.busy}>
                Re-fetch digest
              </button>
            </div>
          )}
        </div>
      </section>
    </div>
  );
}
