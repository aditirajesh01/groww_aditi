import type { SignalKind } from "@/api/types";

interface SignalMeta {
  /** Short label used on the chip. */
  label: string;
  /** What the detector actually measures — shown on hover / in the legend. */
  gloss: string;
  /** Monospace glyph. Deliberately typographic rather than an icon set: it keeps
   *  the card dense and costs zero bytes. */
  glyph: string;
}

export const SIGNAL_META: Record<SignalKind, SignalMeta> = {
  IDIOSYNCRATIC_MOVE: {
    label: "Idiosyncratic",
    gloss: "Return left over after index and sector beta are stripped out — the part that is news about this company.",
    glyph: "↗",
  },
  DRIFT: {
    label: "Drift",
    gloss: "Slow cumulative move that no single-day threshold would ever catch.",
    glyph: "⤳",
  },
  REGIME_CHANGE: {
    label: "Regime change",
    gloss: "Bayesian changepoint on realised volatility — the behaviour of the series changed, not just its level.",
    glyph: "⌇",
  },
  CORRELATION_BREAK: {
    label: "Correlation break",
    gloss: "It stopped moving with the peers it normally moves with.",
    glyph: "≠",
  },
  VOLUME_SURPRISE: {
    label: "Volume",
    gloss: "Participation confirmation — is anyone actually behind the move.",
    glyph: "‖",
  },
  CORPORATE_EVENT: {
    label: "Corporate event",
    gloss: "Earnings, guidance, rating action, block deal, promoter pledge, index change.",
    glyph: "§",
  },
  ABSENCE: {
    label: "Absence",
    gloss: "It was expected to move and did not. Absence is information.",
    glyph: "∅",
  },
  CROWD_FLOW: {
    label: "Crowd flow",
    gloss: "Aggregate, k-anonymised watchlist adds and removes. Minimum cohort 500, never individual.",
    glyph: "≈",
  },
  THESIS_CONTRADICTION: {
    label: "Contradicts your thesis",
    gloss: "Dated evidence pointing against the reason you wrote down. Always shown, never budgeted away.",
    glyph: "✕",
  },
  CORRECTION: {
    label: "Correction",
    gloss: "A number we previously showed you was wrong and has been restated.",
    glyph: "↺",
  },
};

export const PRIORITY_KINDS: SignalKind[] = ["THESIS_CONTRADICTION", "CORRECTION"];

export const isPriorityKind = (k: SignalKind) => PRIORITY_KINDS.includes(k);

/** The signal a dismissal should teach against: the strongest non-priority one. */
export function dismissableKind(kinds: SignalKind[]): SignalKind | null {
  const candidates = kinds.filter((k) => !isPriorityKind(k));
  return candidates[0] ?? null;
}
