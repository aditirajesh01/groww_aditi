import { useId, useState } from "react";
import { AnimatePresence, motion, useReducedMotion } from "motion/react";
import type { Signal } from "@/api/types";
import { SIGNAL_META } from "@/lib/signals";
import { asOf, sigma } from "@/lib/format";
import { heightCollapse } from "@/lib/motion";

export function EvidenceSection({ signals }: { signals: Signal[] }) {
  const [open, setOpen] = useState(false);
  const reduced = useReducedMotion();
  const id = useId();
  const count = signals.reduce((n, s) => n + s.evidence.length, 0);

  return (
    <>
      <button
        type="button"
        aria-expanded={open}
        aria-controls={id}
        onClick={() => setOpen((v) => !v)}
        className="mt-3 flex items-center gap-1.5 text-sm font-semibold text-brand-600 hover:text-brand-700 dark:text-brand-400 dark:hover:text-brand-300"
      >
        <span className={`transition-transform ${open ? "rotate-90" : ""}`} aria-hidden="true">▸</span>
        {open ? "Hide evidence" : "Evidence"}
        <span className="font-mono font-normal text-gray-400">({count})</span>
      </button>

      <AnimatePresence initial={false}>
        {open && (
          <motion.div id={id} {...heightCollapse(!!reduced)}>
            <div className="mt-3 flex flex-col gap-4">
              {signals.map((signal, i) => {
                const meta = SIGNAL_META[signal.kind];
                return (
                  <div key={`${signal.kind}-${i}`} className="rounded-xl border border-gray-100 bg-gray-50/60 p-4 dark:border-gray-800 dark:bg-white/[0.02]">
                    <div className="flex items-center justify-between gap-2">
                      <span className="inline-flex items-center gap-1.5 rounded-full border border-gray-200 bg-white px-2.5 py-1 text-xs font-semibold text-gray-600 dark:border-gray-700 dark:bg-gray-900 dark:text-gray-300">
                        <span aria-hidden="true">{meta.glyph}</span>
                        {meta.label}
                      </span>
                      {signal.z !== 0 && (
                        <span className="font-mono text-xs font-semibold text-gray-500">{sigma(signal.z)}</span>
                      )}
                    </div>
                    <p className="mt-2 text-sm text-gray-700 dark:text-gray-200">{signal.detail}</p>
                    <p className="mt-1 text-xs text-gray-400">{meta.gloss}</p>
                    {signal.evidence.length > 0 && (
                      <ul className="mt-3 flex flex-col gap-2 border-t border-gray-200 pt-3 dark:border-gray-800">
                        {signal.evidence.map((e, j) => (
                          <li key={j} className="flex flex-wrap items-baseline gap-x-2 text-xs">
                            <span className="font-medium text-gray-500 dark:text-gray-400">{e.label}</span>
                            <span className="font-mono font-semibold text-gray-800 dark:text-white">{e.value}</span>
                            <span className="ml-auto flex items-center gap-1.5 text-gray-400">
                              <span>{e.source}</span>
                              <span aria-hidden="true">·</span>
                              <time dateTime={e.as_of}>{asOf(e.as_of)}</time>
                              {e.url && (
                                <>
                                  <span aria-hidden="true">·</span>
                                  <a href={e.url} target="_blank" rel="noreferrer noopener" className="text-brand-600 hover:underline dark:text-brand-400">
                                    source ↗
                                  </a>
                                </>
                              )}
                            </span>
                          </li>
                        ))}
                      </ul>
                    )}
                  </div>
                );
              })}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </>
  );
}
