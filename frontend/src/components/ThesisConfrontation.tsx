import { motion, useReducedMotion } from "motion/react";
import type { ThesisImpact } from "@/api/types";

const VERDICT_WORD: Record<ThesisImpact["verdict"], string> = {
  CONTRADICTS: "against it",
  SUPPORTS: "for it",
  NEUTRAL: "neither way",
};

const BAR_COLOR: Record<ThesisImpact["verdict"], string> = {
  CONTRADICTS: "bg-error-500",
  SUPPORTS: "bg-success-500",
  NEUTRAL: "bg-gray-400",
};

export function ThesisConfrontation({ impact }: { impact: ThesisImpact }) {
  const reduced = useReducedMotion();
  const contradicts = impact.verdict === "CONTRADICTS";

  return (
    <motion.section
      aria-label={`Your thesis, checked against evidence: ${impact.verdict.toLowerCase()}`}
      initial={reduced ? false : { opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={reduced ? { duration: 0 } : { duration: 0.45, ease: [0.16, 1, 0.3, 1], delay: 0.18 }}
      className={
        "mt-4 overflow-hidden rounded-xl border " +
        (contradicts
          ? "border-error-200 bg-error-50/40 dark:border-error-500/25 dark:bg-error-500/[0.04]"
          : "border-gray-200 bg-gray-50/60 dark:border-gray-800 dark:bg-white/[0.02]")
      }
    >
      <div className="grid grid-cols-1 divide-y divide-gray-200 sm:grid-cols-[1fr_auto_1fr] sm:divide-x sm:divide-y-0 dark:divide-gray-800">
        <div className="p-4">
          <span className="text-[11px] font-semibold uppercase tracking-wider text-gray-400">What you wrote</span>
          <blockquote className="mt-1.5 text-[15px] font-medium italic leading-snug text-gray-700 dark:text-gray-200">
            &ldquo;{impact.thesis}&rdquo;
          </blockquote>
        </div>

        <div className="flex items-center justify-center px-2 py-1 text-xs font-semibold uppercase tracking-wide text-gray-400 sm:py-0" aria-hidden="true">
          <motion.span
            initial={reduced ? false : { scale: 0.6, opacity: 0 }}
            animate={{ scale: 1, opacity: 1 }}
            transition={reduced ? { duration: 0 } : { type: "spring", stiffness: 500, damping: 26, delay: 0.42 }}
          >
            {contradicts ? "versus" : "and"}
          </motion.span>
        </div>

        <div className="p-4">
          <span className={`text-[11px] font-semibold uppercase tracking-wider ${contradicts ? "text-error-600 dark:text-error-400" : "text-gray-400"}`}>
            What the record says
          </span>
          <p className="mt-1.5 text-sm leading-snug text-gray-700 dark:text-gray-200">{impact.rationale}</p>
        </div>
      </div>

      <div className="flex flex-wrap items-center justify-between gap-2 border-t border-gray-200 px-4 py-3 dark:border-gray-800">
        <span className="flex items-center gap-2 text-xs font-medium text-gray-500 dark:text-gray-400">
          <span>Evidence points {VERDICT_WORD[impact.verdict]}</span>
          <span className="h-1.5 w-20 overflow-hidden rounded-full bg-gray-200 dark:bg-gray-700" aria-hidden="true">
            <motion.i
              className={`block h-full rounded-full ${BAR_COLOR[impact.verdict]}`}
              initial={reduced ? false : { width: 0 }}
              animate={{ width: `${Math.round(impact.confidence * 100)}%` }}
              transition={reduced ? { duration: 0 } : { duration: 0.8, ease: [0.16, 1, 0.3, 1], delay: 0.5 }}
            />
          </span>
          <span className="font-mono font-semibold text-gray-700 dark:text-gray-200">
            {Math.round(impact.confidence * 100)}%
          </span>
        </span>
      </div>
    </motion.section>
  );
}
