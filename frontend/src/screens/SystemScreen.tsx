import { motion, useReducedMotion } from "motion/react";
import { asOf, FRESHNESS_NOTE } from "@/lib/format";
import { useStore } from "@/state/store";

const STATE_NOTE: Record<string, string> = {
  OK: "Serving normally.",
  RATE_LIMITED: "Throttled. Summaries fall back to the next provider or to the deterministic headline.",
  QUOTA_EXHAUSTED: "Daily cap reached. Cards render from headline + signals only.",
  CIRCUIT_OPEN: "Breaker open after repeated failures. Not being called.",
};

const STATE_TONE: Record<string, string> = {
  OK: "text-success-600 dark:text-success-400",
  RATE_LIMITED: "text-warning-600 dark:text-warning-400",
  QUOTA_EXHAUSTED: "text-warning-600 dark:text-warning-400",
  CIRCUIT_OPEN: "text-error-600 dark:text-error-400",
};

const BAR_TONE: Record<string, string> = {
  OK: "bg-success-500",
  RATE_LIMITED: "bg-warning-500",
  QUOTA_EXHAUSTED: "bg-warning-500",
  CIRCUIT_OPEN: "bg-error-500",
};

function Panel({ title, children, delay = 0 }: { title: string; children: React.ReactNode; delay?: number }) {
  const reduced = useReducedMotion();
  return (
    <motion.div
      initial={reduced ? false : { opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      transition={reduced ? { duration: 0 } : { duration: 0.4, delay }}
      className="rounded-2xl border border-gray-200 bg-white p-6 shadow-sm dark:border-gray-800 dark:bg-gray-900"
    >
      <h2 className="mb-4 text-base font-bold text-gray-800 dark:text-white">{title}</h2>
      {children}
    </motion.div>
  );
}

function Row({ k, v }: { k: string; v: React.ReactNode }) {
  return (
    <div className="flex items-baseline justify-between gap-4 py-1 text-sm">
      <dt className="text-gray-500 dark:text-gray-400">{k}</dt>
      <dd className="m-0 font-mono font-semibold tabular-nums text-gray-800 dark:text-white">{v}</dd>
    </div>
  );
}

export function SystemScreen() {
  const store = useStore();
  const health = store.health;

  return (
    <div className="mx-auto flex max-w-5xl flex-col gap-6 px-6 py-8">
      <h1 className="text-2xl font-extrabold tracking-tight text-gray-800 dark:text-white">System</h1>

      <div className="grid grid-cols-1 gap-6 md:grid-cols-2">
        <Panel title="Market data">
          {health ? (
            <dl>
              <Row k="Source" v={health.market_data.source} />
              <Row k="Freshness" v={health.market_data.freshness} />
              <Row k="As of" v={asOf(health.market_data.as_of)} />
              <Row k="Summary cache hit rate (24h)" v={`${(health.cache_hit_rate_24h * 100).toFixed(0)}%`} />
            </dl>
          ) : (
            <div className="h-24 animate-pulse rounded-md bg-gray-100 dark:bg-gray-800" />
          )}
          {health && <p className="mt-4 text-xs text-gray-400">{FRESHNESS_NOTE[health.market_data.freshness]}</p>}
        </Panel>

        <Panel title="Language layer" delay={0.06}>
          {health?.llm_providers.map((p) => {
            const ratio = p.daily_cap > 0 ? Math.min(1, p.used_today / p.daily_cap) : 0;
            return (
              <div key={p.name} className="mb-4 last:mb-0">
                <div className="flex items-baseline justify-between text-sm">
                  <dt className="font-mono text-xs text-gray-500 dark:text-gray-400">{p.name}</dt>
                  <dd className={`m-0 font-mono text-xs font-bold ${STATE_TONE[p.state]}`}>{p.state}</dd>
                </div>
                <div className="mt-1.5 h-1.5 w-full overflow-hidden rounded-full bg-gray-100 dark:bg-gray-800">
                  <motion.i
                    className={`block h-full rounded-full ${BAR_TONE[p.state]}`}
                    initial={{ width: 0 }}
                    animate={{ width: `${ratio * 100}%` }}
                    transition={{ duration: 0.7, ease: [0.16, 1, 0.3, 1] }}
                  />
                </div>
                <span className="mt-1 block text-xs text-gray-400">
                  {p.daily_cap > 0 ? `${p.used_today} / ${p.daily_cap} today` : `${p.used_today} today · no cap`}
                  {p.resets_at && ` · resets ${asOf(p.resets_at)}`}
                </span>
                <p className="mt-0.5 text-xs text-gray-400">{STATE_NOTE[p.state]}</p>
              </div>
            );
          })}
        </Panel>
      </div>

      <div className="rounded-2xl border border-gray-200 bg-white p-6 shadow-sm dark:border-gray-800 dark:bg-gray-900">
        <h2 className="mb-4 text-base font-bold text-gray-800 dark:text-white">Client</h2>
        <dl>
          <Row k="Data source" v={store.mode === "fixtures" ? "contracts/fixtures/*.json" : "live API"} />
          <Row k="Attention budget" v={`${store.budget.shown} / ${store.budget.cap}`} />
          <Row k="Suppressed this digest" v={store.budget.suppressed} />
          <Row k="Unread in view" v={store.unread} />
        </dl>
        {store.mode === "fixtures" && (
          <div className="mt-4 flex flex-wrap gap-2">
            <button
              onClick={() => void store.advanceSim(6)}
              disabled={store.busy}
              className="rounded-lg bg-brand-500 px-3 py-1.5 text-xs font-semibold text-white hover:bg-brand-600 disabled:opacity-50"
            >
              Advance replay clock 6h
            </button>
            <button
              onClick={() => void store.refresh()}
              disabled={store.busy}
              className="rounded-lg border border-gray-200 px-3 py-1.5 text-xs font-medium text-gray-600 hover:bg-gray-50 disabled:opacity-50 dark:border-gray-700 dark:text-gray-300"
            >
              Re-fetch digest
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
