import { motion, useReducedMotion } from "motion/react";
import type { DigestResponse } from "@/api/types";
import { asOf, MARKET_LABEL, since } from "@/lib/format";
import { Ticker } from "./Ticker";

/**
 * The header's only job is to answer, plainly, two questions the user actually
 * has: how long has it been, and what did you decide not to show me. Stating
 * the suppression out loud is what makes an attention budget trustworthy rather
 * than merely opinionated.
 */
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

  return (
    <header className="digest-head">
      <motion.p
        className="digest-head__lead"
        initial={reduced ? false : { opacity: 0, y: 10 }}
        animate={{ opacity: 1, y: 0 }}
        transition={reduced ? { duration: 0 } : { duration: 0.55, ease: [0.16, 1, 0.3, 1] }}
      >
        {digest.last_checked_at ? (
          <>
            <em>{elapsed}</em> since you last checked.
            <br />
            {shown === 0
              ? "Nothing is waiting for you."
              : `${shown} ${shown === 1 ? "change is" : "changes are"} worth your attention.`}
          </>
        ) : (
          <>
            Your first digest.
            <br />
            {shown} {shown === 1 ? "change" : "changes"} cleared the two-factor gate.
          </>
        )}
      </motion.p>

      <div className="stat-row">
        <div className="stat">
          <span className="stat__v num">
            <Ticker value={shown} decimals={0} from={0} duration={0.6} />
            <span style={{ color: "var(--ink-3)", fontSize: "0.75em" }}> / {cap}</span>
          </span>
          <span className="stat__k">attention budget</span>
          <div className="budget-slots" aria-hidden="true">
            {Array.from({ length: cap }, (_, i) => (
              <motion.i
                key={i}
                data-filled={i < shown}
                initial={reduced ? false : { scaleX: 0 }}
                animate={{ scaleX: 1 }}
                transition={
                  reduced ? { duration: 0 } : { duration: 0.3, delay: 0.2 + i * 0.05, ease: [0.16, 1, 0.3, 1] }
                }
                style={{ originX: 0 }}
              />
            ))}
          </div>
        </div>

        <div className="stat">
          <span className="stat__v num">
            <Ticker value={suppressed} decimals={0} from={0} duration={0.6} />
          </span>
          <span className="stat__k">suppressed</span>
        </div>

        <div className="stat">
          <span className="stat__v num">
            <Ticker value={quietCount} decimals={0} from={0} duration={0.6} />
          </span>
          <span className="stat__k">quiet</span>
        </div>

        {cleared > 0 && (
          <div className="stat">
            <span className="stat__v num" style={{ color: "var(--pos)" }}>
              <Ticker value={cleared} decimals={0} from={0} duration={0.6} />
            </span>
            <span className="stat__k">cleared today</span>
          </div>
        )}

        <div className="stat" style={{ marginInlineStart: "auto", textAlign: "right" }}>
          <span
            className="stat__v num"
            style={{ color: digest.market.nifty_pct >= 0 ? "var(--pos)" : "var(--neg)" }}
          >
            <Ticker value={digest.market.nifty_pct} signed suffix="%" from={0} duration={0.7} />
          </span>
          <span className="stat__k">
            Nifty 50 · {MARKET_LABEL[digest.market.state]}
          </span>
          <span className="stat__k" style={{ opacity: 0.7 }}>
            {asOf(digest.market.as_of)}
          </span>
        </div>
      </div>
    </header>
  );
}
