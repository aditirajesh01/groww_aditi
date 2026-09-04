import type { Direction, Freshness, MarketState } from "@/api/types";

const inr = new Intl.NumberFormat("en-IN", {
  minimumFractionDigits: 2,
  maximumFractionDigits: 2,
});

export const money = (n: number) => inr.format(n);

export function pct(n: number, digits = 2): string {
  const sign = n > 0 ? "+" : n < 0 ? "−" : "";
  return `${sign}${Math.abs(n).toFixed(digits)}%`;
}

export function sigma(z: number): string {
  const sign = z > 0 ? "+" : z < 0 ? "−" : "";
  return `${sign}${Math.abs(z).toFixed(1)}σ`;
}

export function directionOf(n: number | null | undefined): Direction {
  if (n == null || Math.abs(n) < 0.005) return "neutral";
  return n > 0 ? "up" : "down";
}

/** "4 days ago", "3 hours ago" — the header's whole job is answering "how long?". */
export function since(iso: string | null, now = Date.now()): string {
  if (!iso) return "your first check";
  const ms = now - Date.parse(iso);
  if (!Number.isFinite(ms)) return "an unknown time";
  const mins = Math.round(ms / 60000);
  if (mins < 1) return "moments";
  if (mins < 60) return `${mins} minute${mins === 1 ? "" : "s"}`;
  const hours = Math.round(mins / 60);
  if (hours < 36) return `${hours} hour${hours === 1 ? "" : "s"}`;
  const days = Math.round(hours / 24);
  if (days < 14) return `${days} day${days === 1 ? "" : "s"}`;
  const weeks = Math.round(days / 7);
  if (weeks < 9) return `${weeks} week${weeks === 1 ? "" : "s"}`;
  const months = Math.round(days / 30);
  return `${months} month${months === 1 ? "" : "s"}`;
}

const stamp = new Intl.DateTimeFormat("en-IN", {
  day: "2-digit",
  month: "short",
  hour: "2-digit",
  minute: "2-digit",
  hour12: false,
  timeZone: "Asia/Kolkata",
});

const dayOnly = new Intl.DateTimeFormat("en-IN", {
  day: "numeric",
  month: "short",
  year: "numeric",
  timeZone: "Asia/Kolkata",
});

/** Every claim carries a timestamp. This is the one that renders it. */
export const asOf = (iso: string) => `${stamp.format(new Date(iso))} IST`;
export const day = (iso: string) => dayOnly.format(new Date(iso));

export const MARKET_LABEL: Record<MarketState, string> = {
  PRE: "Pre-open",
  OPEN: "Market open",
  POST: "Post-close",
  CLOSED: "Market closed",
};

export const FRESHNESS_LABEL: Record<Freshness, string> = {
  LIVE: "Live",
  DELAYED: "Delayed",
  STALE: "Stale",
  SUSPECT: "Suspect",
};

export const FRESHNESS_NOTE: Record<Freshness, string> = {
  LIVE: "Streaming from the exchange feed.",
  DELAYED: "Last print is behind the exchange feed.",
  STALE: "No fresh print received. Shown rather than blocked.",
  SUSPECT: "Sources disagree beyond tolerance. Derived signals are suppressed.",
};

/** 0..100 attention, bucketed. Drives colour, never wording. */
export type Severity = "low" | "moderate" | "high" | "critical";

export function severity(attention: number): Severity {
  if (attention >= 85) return "critical";
  if (attention >= 65) return "high";
  if (attention >= 40) return "moderate";
  return "low";
}

export const SEVERITY_LABEL: Record<Severity, string> = {
  low: "Low",
  moderate: "Moderate",
  high: "High",
  critical: "Top of budget",
};
