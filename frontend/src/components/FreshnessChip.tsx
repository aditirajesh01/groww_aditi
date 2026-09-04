import { motion, useReducedMotion } from "motion/react";
import type { Provenance } from "@/api/types";
import { asOf, FRESHNESS_LABEL, FRESHNESS_NOTE } from "@/lib/format";

/**
 * Freshness is rendered, never hidden — §8 of the design.
 *
 * LIVE pulses gently (a heartbeat, not a blink). SUSPECT gets a treatment that
 * is deliberately unlike the others: hazard hatching, a colour used for nothing
 * else, a slow flicker. It should look wrong, because it is.
 */
export function FreshnessChip({ provenance }: { provenance: Provenance }) {
  const reduced = useReducedMotion();
  const { freshness, source, as_of, disagreement_pct } = provenance;

  const title =
    `${FRESHNESS_NOTE[freshness]} Source: ${source}. As of ${asOf(as_of)}.` +
    (disagreement_pct != null ? ` Sources differ by ${disagreement_pct}%.` : "") +
    (provenance.corporate_action_adjusted
      ? " Corporate-action adjusted."
      : " NOT corporate-action adjusted.");

  return (
    <span className="fresh" data-freshness={freshness} title={title}>
      {freshness === "LIVE" && !reduced ? (
        <motion.i
          className="fresh__dot"
          animate={{ opacity: [1, 0.25, 1], scale: [1, 0.72, 1] }}
          transition={{ duration: 2.2, repeat: Infinity, ease: "easeInOut" }}
        />
      ) : (
        <i className="fresh__dot" />
      )}
      {FRESHNESS_LABEL[freshness]}
      {freshness === "SUSPECT" && disagreement_pct != null && (
        <span className="num">&nbsp;Δ{disagreement_pct}%</span>
      )}
      <span className="visually-hidden">{title}</span>
    </span>
  );
}
