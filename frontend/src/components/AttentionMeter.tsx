import { motion, useReducedMotion } from "motion/react";
import { severity, SEVERITY_LABEL } from "@/lib/format";
import { Ticker } from "./Ticker";

const FILL: Record<string, string> = {
  low: "bg-gray-300 dark:bg-gray-600",
  moderate: "bg-brand-400",
  high: "bg-warning-500",
  critical: "bg-error-500",
};

export function AttentionMeter({ attention, rank }: { attention: number; rank: number }) {
  const reduced = useReducedMotion();
  const sev = severity(attention);

  return (
    <div className="flex w-16 flex-none flex-col items-center gap-2 border-r border-gray-100 bg-gray-50/60 px-2 py-4 dark:border-gray-800 dark:bg-white/[0.02]">
      <div className="text-center">
        <div className="font-mono text-lg font-bold tabular-nums text-gray-800 dark:text-white">
          <Ticker value={attention} decimals={0} />
        </div>
        <div className="text-[10px] font-semibold uppercase tracking-wider text-gray-400">ATTN</div>
      </div>
      <div
        className="relative h-20 w-1.5 overflow-hidden rounded-full bg-gray-200 dark:bg-gray-800"
        role="meter"
        aria-valuenow={attention}
        aria-valuemin={0}
        aria-valuemax={100}
        aria-label={`Attention score ${attention} of 100 — ${SEVERITY_LABEL[sev]} priority, ranked ${rank}`}
      >
        <motion.i
          className={`absolute bottom-0 left-0 w-full rounded-full ${FILL[sev]}`}
          initial={reduced ? false : { height: "0%" }}
          animate={{ height: `${Math.max(3, Math.min(100, attention))}%` }}
          transition={reduced ? { duration: 0 } : { duration: 0.95, ease: [0.16, 1, 0.3, 1], delay: 0.12 }}
        />
      </div>
      <div className="text-[10px] font-semibold uppercase tracking-wider text-gray-400" title={`Rank ${rank} in this digest`}>
        #{rank}
      </div>
    </div>
  );
}
