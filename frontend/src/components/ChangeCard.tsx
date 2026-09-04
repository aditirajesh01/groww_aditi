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
  onAck?: (item: ChangeItem) => void;
  onDismiss?: (item: ChangeItem, kind: SignalKind) => void;
  readOnly?: boolean;
  showActions?: boolean;
}

const SUMMARY_ABSENT: Record<"PENDING" | "UNAVAILABLE", string> = {
  PENDING: "Plain-language summary is still generating. Everything below is computed deterministically and does not depend on it.",
  UNAVAILABLE: "Summary unavailable — the language layer is rate-limited. The headline, signals and evidence below are unaffected.",
};

const DELTA_TONE: Record<string, string> = {
  up: "text-success-600 dark:text-success-400",
  down: "text-error-600 dark:text-error-400",
  neutral: "text-gray-400",
};

function chipClass(active = false) {
  return active
    ? "inline-flex items-center gap-1 rounded-full border border-success-200 bg-success-50 px-2.5 py-1 text-xs font-semibold text-success-700 dark:border-success-500/30 dark:bg-success-500/10 dark:text-success-400"
    : "inline-flex items-center gap-1 rounded-full border border-gray-200 bg-gray-50 px-2.5 py-1 text-xs font-medium text-gray-600 dark:border-gray-700 dark:bg-white/5 dark:text-gray-300";
}

export function ChangeCard({
  item,
  rank,
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
  const dirTone = DELTA_TONE[dir > 0 ? "up" : dir < 0 ? "down" : "neutral"];

  function handleDragEnd(_: unknown, info: PanInfo) {
    setDragging(false);
    const far = Math.abs(info.offset.x) > 120;
    const fast = Math.abs(info.velocity.x) > 550;
    if (!far && !fast) return;
    if (info.offset.x < 0 && canDismiss && dismissKind) onDismiss?.(item, dismissKind);
    else if (info.offset.x > 0 && canAck) onAck?.(item);
  }

  return (
    <div className="relative">
      {!readOnly && (
        <>
          <motion.div
            className="absolute inset-y-0 right-0 flex items-center pr-5 text-sm font-semibold text-success-600"
            style={{ opacity: rightHint }}
            aria-hidden="true"
          >
            mark read →
          </motion.div>
          <motion.div
            className="absolute inset-y-0 left-0 flex items-center pl-5 text-sm font-semibold text-gray-400"
            style={{ opacity: leftHint }}
            aria-hidden="true"
          >
            ← show fewer
          </motion.div>
        </>
      )}

      <motion.article
        className={
          "relative grid grid-cols-[4rem_1fr] overflow-hidden rounded-2xl border bg-white shadow-sm dark:bg-gray-900 " +
          (isContradiction
            ? "border-error-200 dark:border-error-500/30"
            : isCorrection
              ? "border-warning-200 dark:border-warning-500/30"
              : "border-gray-200 dark:border-gray-800")
        }
        drag={reduced || readOnly ? false : "x"}
        dragDirectionLock
        dragElastic={0.14}
        dragMomentum={false}
        dragConstraints={{ left: canDismiss ? -260 : 0, right: canAck ? 260 : 0 }}
        onDragStart={() => setDragging(true)}
        onDragEnd={handleDragEnd}
        style={{ x, rotate: reduced ? 0 : tilt, cursor: dragging ? "grabbing" : undefined }}
        whileDrag={{ boxShadow: "0 20px 40px -15px rgb(0 0 0 / 0.25)" }}
        aria-labelledby={`h-${item.event_id}`}
      >
        <AttentionMeter attention={item.attention} rank={rank} />

        <div className="min-w-0 p-5">
          <header className="flex flex-wrap items-start justify-between gap-4">
            <div className="min-w-0">
              <div className="flex flex-wrap items-center gap-2">
                <a
                  href={href({ name: "symbol", symbol: item.symbol })}
                  className="font-mono text-sm font-bold text-gray-800 hover:text-brand-600 dark:text-white dark:hover:text-brand-400"
                >
                  {item.symbol}
                </a>
                <span className="text-sm text-gray-400">{item.name}</span>
                {item.is_unread && (
                  <span className="rounded-full bg-brand-500 px-2 py-0.5 text-[10px] font-bold uppercase tracking-wide text-white">
                    New
                  </span>
                )}
              </div>
              <div className="mt-2 flex flex-wrap gap-1.5">
                <FreshnessChip provenance={item.provenance} />
                {!item.provenance.corporate_action_adjusted && (
                  <span className="inline-flex items-center rounded-full border border-warning-200 bg-warning-50 px-2.5 py-0.5 text-xs font-semibold text-warning-700 dark:border-warning-500/30 dark:bg-warning-500/10 dark:text-warning-400">
                    Not CA-adjusted
                  </span>
                )}
              </div>
            </div>

            <div className="flex-none text-right">
              <div className="font-mono text-xl font-bold tabular-nums text-gray-800 dark:text-white">
                <span className="mr-0.5 text-base font-semibold text-gray-400">₹</span>
                <Ticker value={item.price.last} grouped />
              </div>
              <div className="mt-0.5 flex items-center justify-end gap-1.5 text-xs">
                <span className="text-gray-400">
                  {item.price.since_last_seen_pct != null ? "since you last checked" : "today"}
                </span>
                <span className={`font-mono font-semibold ${dirTone}`}>
                  <Ticker value={item.price.since_last_seen_pct ?? item.price.change_pct} signed suffix="%" />
                </span>
              </div>
              {item.price.idiosyncratic_pct != null && (
                <div className="mt-0.5 flex items-center justify-end gap-1.5 text-xs">
                  <span className="text-gray-400">of which idiosyncratic</span>
                  <span className={`font-mono font-semibold ${DELTA_TONE[item.price.idiosyncratic_pct > 0 ? "up" : item.price.idiosyncratic_pct < 0 ? "down" : "neutral"]}`}>
                    <Ticker value={item.price.idiosyncratic_pct} signed suffix="%" />
                  </span>
                </div>
              )}
            </div>
          </header>

          {isCorrection && (
            <div className="mt-3">
              <span className="inline-flex items-center gap-1.5 rounded-full border border-warning-200 bg-warning-50 px-2.5 py-1 text-xs font-bold text-warning-700 dark:border-warning-500/30 dark:bg-warning-500/10 dark:text-warning-400">
                <span aria-hidden="true">↺</span>
                Correction — we got this wrong
              </span>
            </div>
          )}

          <h3 id={`h-${item.event_id}`} className="mt-3 text-lg font-bold leading-snug tracking-tight text-gray-800 dark:text-white">
            {item.headline}
          </h3>

          {item.summary_state === "READY" && item.summary ? (
            <p className="mt-2 text-sm leading-relaxed text-gray-600 dark:text-gray-300">{item.summary}</p>
          ) : (
            <p className="mt-2 flex items-start gap-1.5 text-sm italic text-gray-400">
              <span aria-hidden="true">{item.summary_state === "PENDING" ? "◴" : "⚠"}</span>
              {SUMMARY_ABSENT[item.summary_state === "PENDING" ? "PENDING" : "UNAVAILABLE"]}
            </p>
          )}

          {item.thesis_impact && <ThesisConfrontation impact={item.thesis_impact} />}

          <div className="mt-3 flex flex-wrap gap-1.5">
            <span
              className={chipClass(item.confirmations >= 2)}
              title="Two independent confirming factors are required before anything is promoted into your digest."
            >
              <b>{item.confirmations}</b>
              {item.confirmations === 1 ? " factor" : " factors"}
              {item.confirmations >= 2 ? " confirm" : " — below gate"}
            </span>
            {kinds.map((k) => (
              <span key={k} className={chipClass(isPriorityKind(k))} title={SIGNAL_META[k].gloss}>
                <span aria-hidden="true">{SIGNAL_META[k].glyph}</span>
                {SIGNAL_META[k].label}
              </span>
            ))}
            <span className={chipClass()} title={`First detected ${asOf(item.first_seen)}`}>
              first seen {since(item.first_seen)} ago
            </span>
          </div>

          <EvidenceSection signals={item.signals} />

          {showActions && !readOnly && (
            <div className="mt-4 flex flex-wrap items-center gap-2 border-t border-gray-100 pt-4 dark:border-gray-800">
              {canAck && (
                <button
                  type="button"
                  onClick={() => onAck?.(item)}
                  className="rounded-lg bg-brand-500 px-3.5 py-2 text-sm font-semibold text-white shadow-sm hover:bg-brand-600"
                >
                  Got it
                </button>
              )}
              {canDismiss && dismissKind && (
                <button
                  type="button"
                  onClick={() => onDismiss?.(item, dismissKind)}
                  title={`Teaches a personal threshold for ${SIGNAL_META[dismissKind].label} on ${item.symbol}.`}
                  className="rounded-lg border border-gray-200 px-3.5 py-2 text-sm font-medium text-gray-600 hover:bg-gray-50 dark:border-gray-700 dark:text-gray-300 dark:hover:bg-white/5"
                >
                  Show fewer like this
                </button>
              )}
              <a
                href={href({ name: "symbol", symbol: item.symbol })}
                className="rounded-lg border border-gray-200 px-3.5 py-2 text-sm font-medium text-gray-600 hover:bg-gray-50 dark:border-gray-700 dark:text-gray-300 dark:hover:bg-white/5"
              >
                Timeline
              </a>
            </div>
          )}

          {readOnly && (
            <div className="mt-4 flex flex-wrap items-center justify-between gap-2 border-t border-gray-100 pt-4 dark:border-gray-800">
              <span className="font-mono text-xs text-gray-400">{asOf(item.first_seen)}</span>
              <span className="text-xs text-gray-400">
                {item.price.change_abs >= 0 ? "+" : "−"}₹{money(Math.abs(item.price.change_abs))} · {pct(item.price.change_pct)}
              </span>
            </div>
          )}
        </div>
      </motion.article>
    </div>
  );
}
