import { motion, useReducedMotion } from "motion/react";
import type { QuietItem } from "@/api/types";
import { asOf, pct } from "@/lib/format";
import { href } from "@/state/router";
import { FreshnessChip } from "./FreshnessChip";

const TONE: Record<string, string> = {
  up: "text-success-600 dark:text-success-400",
  down: "text-error-600 dark:text-error-400",
  neutral: "text-gray-400",
};

export function QuietList({ items, checkedAt }: { items: QuietItem[]; checkedAt: string }) {
  const reduced = useReducedMotion();
  if (items.length === 0) return null;

  const suspect = items.filter((q) => q.provenance.freshness === "SUSPECT").length;

  return (
    <motion.section
      initial={reduced ? false : { opacity: 0, y: 12 }}
      whileInView={{ opacity: 1, y: 0 }}
      viewport={{ once: true, margin: "-40px" }}
      transition={reduced ? { duration: 0 } : { duration: 0.5, ease: [0.16, 1, 0.3, 1] }}
      className="overflow-hidden rounded-2xl border border-gray-200 bg-white shadow-sm dark:border-gray-800 dark:bg-gray-900"
    >
      <div className="flex flex-wrap items-baseline justify-between gap-2 border-b border-gray-100 px-5 py-4 dark:border-gray-800">
        <h2 className="text-base font-bold text-gray-800 dark:text-white">Checked, and nothing meaningful changed</h2>
        <span className="text-xs text-gray-400">
          {items.length} {items.length === 1 ? "symbol" : "symbols"} · as of {asOf(checkedAt)}
          {suspect > 0 && ` · ${suspect} with unreliable prints`}
        </span>
      </div>
      <ul className="divide-y divide-gray-100 dark:divide-gray-800">
        {items.map((q, i) => (
          <motion.li
            key={q.symbol}
            initial={reduced ? false : { opacity: 0 }}
            whileInView={{ opacity: 1 }}
            viewport={{ once: true }}
            transition={reduced ? { duration: 0 } : { duration: 0.35, delay: i * 0.045 }}
            className="flex flex-wrap items-center gap-3 px-5 py-3"
          >
            <a
              href={href({ name: "symbol", symbol: q.symbol })}
              className="flex items-baseline gap-2 font-mono text-sm font-bold text-gray-800 hover:text-brand-600 dark:text-white dark:hover:text-brand-400"
            >
              {q.symbol}
              <span className="font-sans text-xs font-normal text-gray-400">{q.name}</span>
            </a>
            <span className="flex-1 text-sm text-gray-500 dark:text-gray-400">{q.reason}</span>
            <span className={`font-mono text-sm font-semibold ${TONE[q.change_pct > 0 ? "up" : q.change_pct < 0 ? "down" : "neutral"]}`}>
              {pct(q.change_pct)}
            </span>
            {q.provenance.freshness !== "LIVE" && <FreshnessChip provenance={q.provenance} />}
          </motion.li>
        ))}
      </ul>
    </motion.section>
  );
}
