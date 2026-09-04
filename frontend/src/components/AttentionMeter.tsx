import { motion, useReducedMotion } from "motion/react";
import { severity, SEVERITY_LABEL } from "@/lib/format";
import { Ticker } from "./Ticker";

/**
 * The attention score is the product's central claim — that this item earned
 * one of `budget.cap` slots. So it gets a physical readout: a meter that fills
 * to the score, colour-mapped to severity, in the card's own gutter.
 */
export function AttentionMeter({ attention, rank }: { attention: number; rank: number }) {
  const reduced = useReducedMotion();
  const sev = severity(attention);

  return (
    <div className="rail" aria-hidden="false">
      <div style={{ textAlign: "center" }}>
        <div className="rail__score num">
          <Ticker value={attention} decimals={0} duration={1.05} from={0} />
        </div>
        <div className="rail__unit eyebrow">ATTN</div>
      </div>
      <div
        className="meter"
        data-severity={sev}
        role="meter"
        aria-valuenow={attention}
        aria-valuemin={0}
        aria-valuemax={100}
        aria-label={`Attention score ${attention} of 100 — ${SEVERITY_LABEL[sev]} priority, ranked ${rank}`}
      >
        <motion.i
          className="meter__fill"
          initial={reduced ? false : { height: "0%" }}
          animate={{ height: `${Math.max(3, Math.min(100, attention))}%` }}
          transition={reduced ? { duration: 0 } : { duration: 0.95, ease: [0.16, 1, 0.3, 1], delay: 0.12 }}
        />
      </div>
      <div className="eyebrow" title={`Rank ${rank} in this digest`}>
        #{rank}
      </div>
    </div>
  );
}
