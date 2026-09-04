import { motion, useReducedMotion } from "motion/react";
import type { ThesisImpact } from "@/api/types";
import { day } from "@/lib/format";

const VERDICT_WORD: Record<ThesisImpact["verdict"], string> = {
  CONTRADICTS: "against it",
  SUPPORTS: "for it",
  NEUTRAL: "neither way",
};

/**
 * The emotional peak of the product.
 *
 * The design decision that matters here is the split: the user's own sentence
 * on the left, the dated evidence on the right, a rule between them. We are not
 * telling them what to do — we are placing their words next to the record and
 * letting the gap speak. The evidence side is the only place in the app that
 * uses the ember tint, so a contradiction is recognisable before it is read.
 *
 * It is deliberately never advisory: no verb in this component tells anyone to
 * act. It says what was believed, what was reported, and when.
 */
export function ThesisConfrontation({
  impact,
  thesisAddedAt,
}: {
  impact: ThesisImpact;
  thesisAddedAt?: string | null;
}) {
  const reduced = useReducedMotion();
  const contradicts = impact.verdict === "CONTRADICTS";

  return (
    <motion.section
      className="confront"
      data-verdict={impact.verdict}
      aria-label={`Your thesis, checked against evidence: ${impact.verdict.toLowerCase()}`}
      initial={reduced ? false : { opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={reduced ? { duration: 0 } : { duration: 0.45, ease: [0.16, 1, 0.3, 1], delay: 0.18 }}
    >
      <div className="confront__grid">
        <div className="confront__side confront__side--mine">
          <span className="confront__k">What you wrote</span>
          <blockquote className="confront__quote">{impact.thesis}</blockquote>
          {thesisAddedAt && (
            <span className="confront__when">added {day(thesisAddedAt)}</span>
          )}
        </div>

        <div className="confront__vs" aria-hidden="true">
          <motion.span
            initial={reduced ? false : { scale: 0.6, opacity: 0 }}
            animate={{ scale: 1, opacity: 1 }}
            transition={
              reduced
                ? { duration: 0 }
                : { type: "spring", stiffness: 500, damping: 26, delay: 0.42 }
            }
          >
            {contradicts ? "versus" : "and"}
          </motion.span>
        </div>

        <div className="confront__side confront__side--evidence">
          <span className="confront__k">What the record says</span>
          <p className="confront__evidence">{impact.rationale}</p>
        </div>
      </div>

      <div className="confront__foot">
        <span className="confront__conf">
          <span>evidence points {VERDICT_WORD[impact.verdict]}</span>
          <span className="confbar" aria-hidden="true">
            <motion.i
              initial={reduced ? false : { width: 0 }}
              animate={{ width: `${Math.round(impact.confidence * 100)}%` }}
              transition={reduced ? { duration: 0 } : { duration: 0.8, ease: [0.16, 1, 0.3, 1], delay: 0.5 }}
            />
          </span>
          <span className="num">{Math.round(impact.confidence * 100)}%</span>
        </span>
        <span className="confront__disclaimer">
          Your hypothesis, checked against dated evidence. Not advice.
        </span>
      </div>
    </motion.section>
  );
}
