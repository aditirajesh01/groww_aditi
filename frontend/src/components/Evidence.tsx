import { useId, useState } from "react";
import { AnimatePresence, motion, useReducedMotion } from "motion/react";
import type { Signal } from "@/api/types";
import { SIGNAL_META } from "@/lib/signals";
import { asOf, sigma } from "@/lib/format";
import { heightCollapse } from "@/lib/motion";

/**
 * Every claim on a card traces to a row here, and every row carries its own
 * source and as-of stamp. This is the compliance posture (§8) and the trust
 * mechanism at the same time — nothing is asserted without a citation.
 */
export function EvidenceSection({ signals }: { signals: Signal[] }) {
  const [open, setOpen] = useState(false);
  const reduced = useReducedMotion();
  const id = useId();
  const count = signals.reduce((n, s) => n + s.evidence.length, 0);

  return (
    <>
      <button
        type="button"
        className="evidence-toggle"
        aria-expanded={open}
        aria-controls={id}
        onClick={() => setOpen((v) => !v)}
      >
        <span className="evidence-toggle__caret" aria-hidden="true">
          ▸
        </span>
        {open ? "Hide evidence" : "Evidence"}
        <span className="num" style={{ opacity: 0.7 }}>
          ({count})
        </span>
      </button>

      <AnimatePresence initial={false}>
        {open && (
          <motion.div id={id} className="evidence" {...heightCollapse(!!reduced)}>
            <div className="evidence__inner">
              {signals.map((signal, i) => {
                const meta = SIGNAL_META[signal.kind];
                return (
                  <div className="sig" key={`${signal.kind}-${i}`}>
                    <div className="sig__head">
                      <span className="chip">
                        <span className="chip__glyph" aria-hidden="true">
                          {meta.glyph}
                        </span>
                        {meta.label}
                      </span>
                      {signal.z !== 0 && <span className="sig__z">{sigma(signal.z)}</span>}
                    </div>
                    <p className="sig__detail">{signal.detail}</p>
                    <p className="sig__gloss">{meta.gloss}</p>
                    {signal.evidence.length > 0 && (
                      <ul className="ev-list">
                        {signal.evidence.map((e, j) => (
                          <li className="ev" key={j}>
                            <span className="ev__label">{e.label}</span>
                            <span className="ev__value">{e.value}</span>
                            <span className="ev__meta">
                              <span>{e.source}</span>
                              <span aria-hidden="true">·</span>
                              <time dateTime={e.as_of}>{asOf(e.as_of)}</time>
                              {e.url && (
                                <>
                                  <span aria-hidden="true">·</span>
                                  <a href={e.url} target="_blank" rel="noreferrer noopener">
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
