import { motion, useReducedMotion } from "motion/react";
import type { QuietItem } from "@/api/types";
import { asOf, pct } from "@/lib/format";
import { href } from "@/state/router";
import { FreshnessChip } from "./FreshnessChip";

/**
 * "Nothing meaningful changed" is a real answer, so it gets a real component:
 * every quiet symbol names the specific reason it did not clear the gate, with
 * its own freshness stamp. An empty gap here would read as a bug; a list of
 * checked-and-clear symbols reads as diligence.
 */
export function QuietList({ items, checkedAt }: { items: QuietItem[]; checkedAt: string }) {
  const reduced = useReducedMotion();
  if (items.length === 0) return null;

  const suspect = items.filter((q) => q.provenance.freshness === "SUSPECT").length;

  return (
    <motion.section
      className="quiet"
      initial={reduced ? false : { opacity: 0, y: 12 }}
      whileInView={{ opacity: 1, y: 0 }}
      viewport={{ once: true, margin: "-40px" }}
      transition={reduced ? { duration: 0 } : { duration: 0.5, ease: [0.16, 1, 0.3, 1] }}
    >
      <div className="quiet__head">
        <h2 className="quiet__title">Checked, and nothing meaningful changed</h2>
        <span className="quiet__sub">
          {items.length} {items.length === 1 ? "symbol" : "symbols"} · as of {asOf(checkedAt)}
          {suspect > 0 && ` · ${suspect} with unreliable prints`}
        </span>
      </div>
      <ul className="quiet__list">
        {items.map((q, i) => (
          <motion.li
            className="quiet__row"
            key={q.symbol}
            initial={reduced ? false : { opacity: 0 }}
            whileInView={{ opacity: 1 }}
            viewport={{ once: true }}
            transition={reduced ? { duration: 0 } : { duration: 0.35, delay: i * 0.045 }}
          >
            <a className="quiet__sym" href={href({ name: "symbol", symbol: q.symbol })}>
              {q.symbol}
              <span className="quiet__name">{q.name}</span>
            </a>
            <span className="quiet__reason">{q.reason}</span>
            <span
              className={`quiet__pct ${q.change_pct > 0 ? "up" : q.change_pct < 0 ? "down" : "neutral"}`}
            >
              {pct(q.change_pct)}
            </span>
            {q.provenance.freshness !== "LIVE" && (
              <span className="quiet__flags">
                <FreshnessChip provenance={q.provenance} />
              </span>
            )}
          </motion.li>
        ))}
      </ul>
    </motion.section>
  );
}
