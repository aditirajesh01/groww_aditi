import { useEffect, useRef } from "react";
import { animate, useReducedMotion } from "motion/react";
import { EASE_OUT } from "@/lib/motion";

interface Props {
  value: number;
  /** Decimal places. */
  decimals?: number;
  /** Render a leading + / − and always show the sign. */
  signed?: boolean;
  suffix?: string;
  prefix?: string;
  /** Group with Indian digit grouping (lakh/crore). Off for percentages. */
  grouped?: boolean;
  duration?: number;
  className?: string;
  /** Count from this instead of zero — used for deltas so they sweep from flat. */
  from?: number;
}

const grouper = new Intl.NumberFormat("en-IN", {
  minimumFractionDigits: 2,
  maximumFractionDigits: 2,
});

/**
 * Numbers count up rather than snapping into place. The reason is not delight:
 * a price that animates from a neutral origin makes the *direction* and the
 * *magnitude* legible before you have read the digits. Reduced motion writes
 * the final value immediately, and the DOM text is written through a ref so a
 * 60fps count does not trigger 60 React renders.
 */
export function Ticker({
  value,
  decimals = 2,
  signed = false,
  suffix = "",
  prefix = "",
  grouped = false,
  duration = 0.85,
  className,
  from,
}: Props) {
  const ref = useRef<HTMLSpanElement>(null);
  const current = useRef<number | null>(null);
  const reduced = useReducedMotion();

  const fmt = (n: number) => {
    const abs = Math.abs(n);
    const body =
      grouped && decimals === 2
        ? grouper.format(abs)
        : abs.toFixed(decimals);
    const sign = signed ? (n > 0 ? "+" : n < 0 ? "−" : "") : n < 0 ? "−" : "";
    return `${sign}${prefix}${body}${suffix}`;
  };

  useEffect(() => {
    const node = ref.current;
    if (!node) return;
    const start = current.current ?? from ?? (signed ? 0 : value * 0.985);

    if (reduced || start === value) {
      node.textContent = fmt(value);
      current.current = value;
      return;
    }

    const controls = animate(start, value, {
      duration,
      ease: EASE_OUT,
      onUpdate: (v) => {
        node.textContent = fmt(v);
        current.current = v;
      },
      onComplete: () => {
        node.textContent = fmt(value);
        current.current = value;
      },
    });
    return () => controls.stop();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [value, reduced, decimals, signed, suffix, prefix, grouped, duration]);

  return (
    <span ref={ref} className={className}>
      {fmt(reduced ? value : (from ?? (signed ? 0 : value)))}
    </span>
  );
}
