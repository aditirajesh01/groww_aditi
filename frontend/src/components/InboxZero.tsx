import { motion, useReducedMotion } from "motion/react";
import { Ticker } from "./Ticker";

/**
 * Inbox zero has to be earned, so it is not a shrug and an empty div. The mark
 * draws itself once — a single stroke completing — and the numbers underneath
 * are the receipt: what you read, what the system chose not to bother you with.
 * Read what you have seen and it is gone. This is the screen that proves it.
 */
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
      className="zero"
      initial={reduced ? false : { opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      transition={reduced ? { duration: 0 } : { duration: 0.6, ease: [0.16, 1, 0.3, 1] }}
      aria-live="polite"
    >
      <svg className="zero__mark" viewBox="0 0 48 48" fill="none" aria-hidden="true">
        <motion.circle
          cx="24"
          cy="24"
          r="20"
          stroke="var(--hair-strong)"
          strokeWidth="1.5"
          initial={reduced ? false : { pathLength: 0, opacity: 0 }}
          animate={{ pathLength: 1, opacity: 1 }}
          transition={reduced ? { duration: 0 } : { duration: 0.7, ease: "easeInOut" }}
          style={{ rotate: -90, originX: "24px", originY: "24px" }}
        />
        <motion.path
          d="M15 24.5 L21.5 31 L33.5 18"
          stroke="var(--brass)"
          strokeWidth="2.4"
          strokeLinecap="round"
          strokeLinejoin="round"
          initial={reduced ? false : { pathLength: 0 }}
          animate={{ pathLength: 1 }}
          transition={reduced ? { duration: 0 } : { duration: 0.45, delay: 0.5, ease: [0.16, 1, 0.3, 1] }}
        />
      </svg>

      <h2 className="zero__title">You are current.</h2>
      <p className="zero__body">
        Every change since your last check has been read. The cursor only moves forward, so none of
        it will come back to ask again.
      </p>

      <div className="zero__stats">
        <div className="stat">
          <span className="stat__v num" style={{ color: "var(--pos)" }}>
            <Ticker value={cleared} decimals={0} from={0} duration={0.9} />
          </span>
          <span className="stat__k">read this session</span>
        </div>
        <div className="stat">
          <span className="stat__v num">
            <Ticker value={suppressed} decimals={0} from={0} duration={0.9} />
          </span>
          <span className="stat__k">never shown to you</span>
        </div>
        <div className="stat">
          <span className="stat__v num">
            <Ticker value={quiet} decimals={0} from={0} duration={0.9} />
          </span>
          <span className="stat__k">checked and quiet</span>
        </div>
      </div>

      <div className="zero__actions">
        <button type="button" className="btn" onClick={onRefresh} disabled={busy}>
          Check again
        </button>
        {canAdvance && onAdvance && (
          <button type="button" className="btn btn--ghost" onClick={() => onAdvance(6)} disabled={busy}>
            Advance replay clock 6h
          </button>
        )}
      </div>
    </motion.section>
  );
}
