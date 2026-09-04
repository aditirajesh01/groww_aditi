import { motion, useReducedMotion } from "motion/react";
import { Ticker } from "./Ticker";

export function InboxZero({
  cleared,
  suppressed,
  quiet,
  onRefresh,
  onAdvance,
  canAdvance,
  busy,
}: {
  cleared: number;
  suppressed: number;
  quiet: number;
  onRefresh: () => void;
  onAdvance?: (hours: number) => void;
  canAdvance: boolean;
  busy: boolean;
}) {
  const reduced = useReducedMotion();

  return (
    <motion.section
      initial={reduced ? false : { opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      transition={reduced ? { duration: 0 } : { duration: 0.6, ease: [0.16, 1, 0.3, 1] }}
      aria-live="polite"
      className="flex flex-col items-center rounded-2xl border border-gray-200 bg-white px-6 py-14 text-center shadow-sm dark:border-gray-800 dark:bg-gray-900"
    >
      <svg width="48" height="48" viewBox="0 0 48 48" fill="none" aria-hidden="true" className="mb-5">
        <motion.circle
          cx="24" cy="24" r="20" stroke="currentColor" strokeWidth="1.5" className="text-gray-200 dark:text-gray-700"
          initial={reduced ? false : { pathLength: 0, opacity: 0 }}
          animate={{ pathLength: 1, opacity: 1 }}
          transition={reduced ? { duration: 0 } : { duration: 0.7, ease: "easeInOut" }}
          style={{ rotate: -90, originX: "24px", originY: "24px" }}
        />
        <motion.path
          d="M15 24.5 L21.5 31 L33.5 18" stroke="currentColor" strokeWidth="2.4"
          strokeLinecap="round" strokeLinejoin="round" className="text-brand-500"
          initial={reduced ? false : { pathLength: 0 }}
          animate={{ pathLength: 1 }}
          transition={reduced ? { duration: 0 } : { duration: 0.45, delay: 0.5, ease: [0.16, 1, 0.3, 1] }}
        />
      </svg>

      <h2 className="text-2xl font-bold tracking-tight text-gray-800 dark:text-white">You are current.</h2>
      <p className="mt-2 max-w-md text-sm text-gray-500 dark:text-gray-400">
        Every change since your last check has been read. The cursor only moves forward, so none of it
        will come back to ask again.
      </p>

      <div className="mt-8 flex flex-wrap justify-center gap-8">
        <div>
          <div className="font-mono text-2xl font-bold tabular-nums text-success-600 dark:text-success-400">
            <Ticker value={cleared} decimals={0} />
          </div>
          <div className="mt-1 text-xs font-medium text-gray-400">read this session</div>
        </div>
        <div>
          <div className="font-mono text-2xl font-bold tabular-nums text-gray-800 dark:text-white">
            <Ticker value={suppressed} decimals={0} />
          </div>
          <div className="mt-1 text-xs font-medium text-gray-400">never shown to you</div>
        </div>
        <div>
          <div className="font-mono text-2xl font-bold tabular-nums text-gray-800 dark:text-white">
            <Ticker value={quiet} decimals={0} />
          </div>
          <div className="mt-1 text-xs font-medium text-gray-400">checked and quiet</div>
        </div>
      </div>

      <div className="mt-8 flex flex-wrap justify-center gap-2">
        <button
          type="button"
          onClick={onRefresh}
          disabled={busy}
          className="rounded-lg bg-brand-500 px-4 py-2.5 text-sm font-semibold text-white shadow-sm hover:bg-brand-600 disabled:opacity-50"
        >
          Check again
        </button>
        {canAdvance && onAdvance && (
          <button
            type="button"
            onClick={() => onAdvance(6)}
            disabled={busy}
            className="rounded-lg border border-gray-200 px-4 py-2.5 text-sm font-medium text-gray-600 hover:bg-gray-50 disabled:opacity-50 dark:border-gray-700 dark:text-gray-300 dark:hover:bg-white/5"
          >
            Advance replay clock 6h
          </button>
        )}
      </div>
    </motion.section>
  );
}
