import { motion, useReducedMotion } from "motion/react";
import type { Provenance } from "@/api/types";
import { asOf, FRESHNESS_LABEL, FRESHNESS_NOTE } from "@/lib/format";

const TONE: Record<Provenance["freshness"], string> = {
  LIVE: "border-success-200 bg-success-50 text-success-700 dark:border-success-500/30 dark:bg-success-500/10 dark:text-success-400",
  DELAYED: "border-warning-200 bg-warning-50 text-warning-700 dark:border-warning-500/30 dark:bg-warning-500/10 dark:text-warning-400",
  STALE: "border-gray-200 bg-gray-100 text-gray-500 dark:border-gray-700 dark:bg-gray-800 dark:text-gray-400",
  SUSPECT: "border-error-200 bg-error-50 text-error-700 dark:border-error-500/30 dark:bg-error-500/10 dark:text-error-400",
};

const DOT: Record<Provenance["freshness"], string> = {
  LIVE: "bg-success-500",
  DELAYED: "bg-warning-500",
  STALE: "bg-gray-400",
  SUSPECT: "bg-error-500",
};

export function FreshnessChip({ provenance }: { provenance: Provenance }) {
  const reduced = useReducedMotion();
  const { freshness, source, as_of, disagreement_pct } = provenance;

  const title =
    `${FRESHNESS_NOTE[freshness]} Source: ${source}. As of ${asOf(as_of)}.` +
    (disagreement_pct != null ? ` Sources differ by ${disagreement_pct}%.` : "") +
    (provenance.corporate_action_adjusted ? " Corporate-action adjusted." : " NOT corporate-action adjusted.");

  return (
    <span
      title={title}
      className={`inline-flex items-center gap-1.5 rounded-full border px-2.5 py-0.5 text-xs font-semibold ${TONE[freshness]}`}
    >
      {freshness === "LIVE" && !reduced ? (
        <motion.i
          className={`h-1.5 w-1.5 rounded-full ${DOT[freshness]}`}
          animate={{ opacity: [1, 0.25, 1], scale: [1, 0.72, 1] }}
          transition={{ duration: 2.2, repeat: Infinity, ease: "easeInOut" }}
        />
      ) : (
        <i className={`h-1.5 w-1.5 rounded-full ${DOT[freshness]}`} />
      )}
      {FRESHNESS_LABEL[freshness]}
      {freshness === "SUSPECT" && disagreement_pct != null && (
        <span className="font-mono">Δ{disagreement_pct}%</span>
      )}
      <span className="sr-only">{title}</span>
    </span>
  );
}
