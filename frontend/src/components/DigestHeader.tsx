import { motion, useReducedMotion } from "motion/react";
import type { DigestResponse } from "@/api/types";
import { asOf, MARKET_LABEL, since } from "@/lib/format";
import { Ticker } from "./Ticker";

export function DigestHeader({
  digest,
  shown,
  suppressed,
  quietCount,
  cleared,
}: {
  digest: DigestResponse;
  shown: number;
  suppressed: number;
  quietCount: number;
  cleared: number;
}) {
  const reduced = useReducedMotion();
  const elapsed = since(digest.last_checked_at, Date.parse(digest.generated_at));
  const cap = digest.budget.cap;
  const marketUp = digest.market.nifty_pct >= 0;

  return (
    <header className="rounded-2xl border border-gray-200 bg-white p-6 shadow-sm dark:border-gray-800 dark:bg-gray-900 sm:p-8">
      <motion.p
        initial={reduced ? false : { opacity: 0, y: 10 }}
        animate={{ opacity: 1, y: 0 }}
        transition={reduced ? { duration: 0 } : { duration: 0.55, ease: [0.16, 1, 0.3, 1] }}
        className="text-2xl font-extrabold leading-tight tracking-tight text-gray-800 dark:text-white sm:text-3xl"
      >
        {digest.last_checked_at ? (
          <>
            <span className="text-brand-500">{elapsed}</span> since you last checked.
            <br />
            {shown === 0 ? "Nothing is waiting for you." : `${shown} ${shown === 1 ? "change is" : "changes are"} worth your attention.`}
          </>
        ) : (
          <>
            Your first digest.
            <br />
            {shown} {shown === 1 ? "change" : "changes"} cleared the two-factor gate.
          </>
        )}
      </motion.p>

      <div className="mt-6 flex flex-wrap items-end gap-x-10 gap-y-5 border-t border-gray-100 pt-5 dark:border-gray-800">
        <div>
          <div className="font-mono text-2xl font-bold tabular-nums text-gray-800 dark:text-white">
            <Ticker value={shown} decimals={0} />
            <span className="text-sm font-medium text-gray-400"> / {cap}</span>
          </div>
          <div className="text-xs font-medium text-gray-400">attention budget</div>
          <div className="mt-1.5 flex gap-1" aria-hidden="true">
            {Array.from({ length: cap }, (_, i) => (
              <motion.i
                key={i}
                className={`h-1.5 w-5 rounded-full origin-left ${i < shown ? "bg-brand-500" : "bg-gray-200 dark:bg-gray-700"}`}
                initial={reduced ? false : { scaleX: 0 }}
                animate={{ scaleX: 1 }}
                transition={reduced ? { duration: 0 } : { duration: 0.3, delay: 0.2 + i * 0.05, ease: [0.16, 1, 0.3, 1] }}
              />
            ))}
          </div>
        </div>

        <div>
          <div className="font-mono text-2xl font-bold tabular-nums text-gray-800 dark:text-white">
            <Ticker value={suppressed} decimals={0} />
          </div>
          <div className="text-xs font-medium text-gray-400">suppressed</div>
        </div>

        <div>
          <div className="font-mono text-2xl font-bold tabular-nums text-gray-800 dark:text-white">
            <Ticker value={quietCount} decimals={0} />
          </div>
          <div className="text-xs font-medium text-gray-400">quiet</div>
        </div>

        {cleared > 0 && (
          <div>
            <div className="font-mono text-2xl font-bold tabular-nums text-success-600 dark:text-success-400">
              <Ticker value={cleared} decimals={0} />
            </div>
            <div className="text-xs font-medium text-gray-400">cleared today</div>
          </div>
        )}

        <div className="ml-auto text-right">
          <div className={`font-mono text-2xl font-bold tabular-nums ${marketUp ? "text-success-600 dark:text-success-400" : "text-error-600 dark:text-error-400"}`}>
            <Ticker value={digest.market.nifty_pct} signed suffix="%" />
          </div>
          <div className="text-xs font-medium text-gray-400">Nifty 50 · {MARKET_LABEL[digest.market.state]}</div>
          <div className="text-xs text-gray-300 dark:text-gray-600">{asOf(digest.market.as_of)}</div>
        </div>
      </div>
    </header>
  );
}
