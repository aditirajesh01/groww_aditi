import { useState } from "react";
import {
  motion,
  useMotionValue,
  useReducedMotion,
  useTransform,
  type PanInfo,
} from "motion/react";
import type { ChangeItem, SignalKind } from "@/api/types";
import { asOf, money, pct, since } from "@/lib/format";
import { dismissableKind, isPriorityKind, SIGNAL_META } from "@/lib/signals";
import { href } from "@/state/router";
import { AttentionMeter } from "./AttentionMeter";
import { EvidenceSection } from "./Evidence";
import { FreshnessChip } from "./FreshnessChip";
import { ThesisConfrontation } from "./ThesisConfrontation";
import { Ticker } from "./Ticker";

interface Props {
  item: ChangeItem;
  rank: number;
  thesisAddedAt?: string | null;
  onAck?: (item: ChangeItem) => void;
  onDismiss?: (item: ChangeItem, kind: SignalKind) => void;
  /** Corrections and detail-page timeline entries are read-only. */
  readOnly?: boolean;
  showActions?: boolean;
}

const SUMMARY_ABSENT: Record<"PENDING" | "UNAVAILABLE", string> = {
  PENDING:
    "Plain-language summary is still generating. Everything below is computed deterministically and does not depend on it.",
  UNAVAILABLE:
    "Summary unavailable — the language layer is rate-limited. The headline, signals and evidence below are unaffected.",
};

export function ChangeCard({
  item,
  rank,
  thesisAddedAt,
  onAck,
  onDismiss,
  readOnly = false,
  showActions = true,
}: Props) {
  const reduced = useReducedMotion();
  const [dragging, setDragging] = useState(false);

  const x = useMotionValue(0);
  const leftHint = useTransform(x, [-140, -40, 0], [1, 0, 0]);
  const rightHint = useTransform(x, [0, 40, 140], [0, 0, 1]);
  const tilt = useTransform(x, [-200, 0, 200], [-1.4, 0, 1.4]);

  const kinds = item.signals.map((s) => s.kind);
  const isCorrection = kinds.includes("CORRECTION");
  const isContradiction = item.thesis_impact?.verdict === "CONTRADICTS";
  const dismissKind = dismissableKind(kinds);
  const canDismiss = !readOnly && !isCorrection && !!dismissKind && !!onDismiss;
  const canAck = !readOnly && !!onAck;

  const dir = item.price.since_last_seen_pct ?? item.price.change_pct;
  const dirClass = dir > 0 ? "up" : dir < 0 ? "down" : "neutral";

  function handleDragEnd(_: unknown, info: PanInfo) {
    setDragging(false);
    const far = Math.abs(info.offset.x) > 120;
    const fast = Math.abs(info.velocity.x) > 550;
    if (!far && !fast) return;
    if (info.offset.x < 0 && canDismiss && dismissKind) onDismiss?.(item, dismissKind);
    else if (info.offset.x > 0 && canAck) onAck?.(item);
  }

  return (
    <div className="card-shell">
      {!readOnly && (
        <>
          <motion.div className="card__swipe" style={{ opacity: rightHint }} aria-hidden="true">
            mark read →
          </motion.div>
          <motion.div
            className="card__swipe"
            style={{
              opacity: leftHint,
              insetInlineEnd: "auto",
              insetInlineStart: 0,
              justifyContent: "flex-start",
              paddingInlineStart: "var(--space-5)",
            }}
            aria-hidden="true"
          >
            ← show fewer
          </motion.div>
        </>
      )}

      <motion.article
        className={[
          "card",
          item.is_unread ? "card--unread" : "",
          isContradiction ? "card--contradiction" : "",
          isCorrection ? "card--correction" : "",
        ]
          .filter(Boolean)
          .join(" ")}
        drag={reduced || readOnly ? false : "x"}
        dragDirectionLock
        dragElastic={0.14}
        dragMomentum={false}
        dragConstraints={{ left: canDismiss ? -260 : 0, right: canAck ? 260 : 0 }}
        onDragStart={() => setDragging(true)}
        onDragEnd={handleDragEnd}
        style={{ x, rotate: reduced ? 0 : tilt, cursor: dragging ? "grabbing" : undefined }}
        whileDrag={{ boxShadow: "var(--shadow-large)" }}
        aria-labelledby={`h-${item.event_id}`}
      >
        <AttentionMeter attention={item.attention} rank={rank} />

        <div className="card__body">
          <header className="card__top">
            <div className="sym">
              <div className="sym__row">
                <a className="sym__ticker" href={href({ name: "symbol", symbol: item.symbol })}>
                  {item.symbol}
                </a>
                <span className="sym__name">{item.name}</span>
                {item.is_unread && (
                  <span className="chip chip--priority" style={{ height: "1.1rem" }}>
                    New
                  </span>
                )}
              </div>
              <div style={{ marginTop: "0.35rem", display: "flex", gap: "0.375rem", flexWrap: "wrap" }}>
                <FreshnessChip provenance={item.provenance} />
                {!item.provenance.corporate_action_adjusted && (
                  <span className="chip chip--correction">Not CA-adjusted</span>
                )}
              </div>
            </div>

            <div className="price">
              <div className="price__last">
                <span className="cur">₹</span>
                <Ticker value={item.price.last} grouped />
              </div>
              <div className="price__delta">
                <span className="price__label">
                  {item.price.since_last_seen_pct != null ? "since you last checked" : "today"}
                </span>
                <span className={dirClass}>
                  <Ticker
                    value={item.price.since_last_seen_pct ?? item.price.change_pct}
                    signed
                    suffix="%"
                    from={0}
                  />
                </span>
              </div>
              {item.price.idiosyncratic_pct != null && (
                <div className="price__delta" style={{ marginTop: "0.15rem" }}>
                  <span className="price__label">of which idiosyncratic</span>
                  <span className={item.price.idiosyncratic_pct > 0 ? "up" : item.price.idiosyncratic_pct < 0 ? "down" : "neutral"}>
                    <Ticker value={item.price.idiosyncratic_pct} signed suffix="%" from={0} />
                  </span>
                </div>
              )}
            </div>
          </header>

          {isCorrection && (
            <div className="chips" style={{ marginTop: "var(--space-4)" }}>
              <span className="chip chip--correction">
                <span className="chip__glyph" aria-hidden="true">
                  ↺
                </span>
                Correction — we got this wrong
              </span>
            </div>
          )}

          <h3 className="headline" id={`h-${item.event_id}`}>
            {item.headline}
          </h3>

          {item.summary_state === "READY" && item.summary ? (
            <p className="summary">{item.summary}</p>
          ) : (
            <p className="summary--absent">
              <span aria-hidden="true">{item.summary_state === "PENDING" ? "◴" : "⚠"}</span>
              {SUMMARY_ABSENT[item.summary_state === "PENDING" ? "PENDING" : "UNAVAILABLE"]}
            </p>
          )}

          {item.thesis_impact && (
            <ThesisConfrontation impact={item.thesis_impact} thesisAddedAt={thesisAddedAt} />
          )}

          <div className="chips">
            <span
              className={`chip ${item.confirmations >= 2 ? "chip--confirm" : ""}`}
              title="Two independent confirming factors are required before anything is promoted into your digest."
            >
              <b>{item.confirmations}</b>
              {item.confirmations === 1 ? " factor" : " factors"}
              {item.confirmations >= 2 ? " confirm" : " — below gate"}
            </span>
            {kinds.map((k) => (
              <span
                key={k}
                className={`chip ${isPriorityKind(k) ? "chip--priority" : ""}`}
                title={SIGNAL_META[k].gloss}
              >
                <span className="chip__glyph" aria-hidden="true">
                  {SIGNAL_META[k].glyph}
                </span>
                {SIGNAL_META[k].label}
              </span>
            ))}
            <span className="chip" title={`First detected ${asOf(item.first_seen)}`}>
              first seen {since(item.first_seen)} ago
            </span>
          </div>

          <EvidenceSection signals={item.signals} />

          {showActions && !readOnly && (
            <div className="card__actions">
              {canAck && (
                <button type="button" className="btn btn--primary btn--sm" onClick={() => onAck?.(item)}>
                  Got it
                </button>
              )}
              {canDismiss && dismissKind && (
                <button
                  type="button"
                  className="btn btn--ghost btn--sm"
                  onClick={() => onDismiss?.(item, dismissKind)}
                  title={`Teaches a personal threshold for ${SIGNAL_META[dismissKind].label} on ${item.symbol}.`}
                >
                  Show fewer like this
                </button>
              )}
              <a className="btn btn--ghost btn--sm" href={href({ name: "symbol", symbol: item.symbol })}>
                Timeline
              </a>
              <span className="card__hint">
                {canDismiss ? "swipe ← fewer · → read" : "swipe → to mark read"}
              </span>
            </div>
          )}

          {readOnly && (
            <div className="card__actions">
              <span className="eyebrow">
                seq {item.seq} · {asOf(item.first_seen)}
              </span>
              <span className="card__hint">
                {item.price.change_abs >= 0 ? "+" : "−"}₹{money(Math.abs(item.price.change_abs))} ·{" "}
                {pct(item.price.change_pct)}
              </span>
            </div>
          )}
        </div>
      </motion.article>
    </div>
  );
}
