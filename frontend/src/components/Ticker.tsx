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
 * Renders a formatted number. Previously animated a count-up via an
 * imperative `motion` `animate()` call in a `useEffect`, written straight to
 * the DOM through a ref to avoid a 60fps React re-render. That worked in the
 * Vite dev server but the animation never ran at all once bundled for
 * production (no error, no update -- every card silently showed 0 / 0.00%
 * on the live deploy). Not worth chasing the bundler-specific cause under
 * demo time pressure: a plain, correct render beats a broken animation.
 */
export function Ticker({
  value,
  decimals = 2,
  signed = false,
  suffix = "",
  prefix = "",
  grouped = false,
  className,
}: Props) {
  const abs = Math.abs(value);
  const body = grouped && decimals === 2 ? grouper.format(abs) : abs.toFixed(decimals);
  const sign = signed ? (value > 0 ? "+" : value < 0 ? "−" : "") : value < 0 ? "−" : "";

  return (
    <span className={className}>
      {sign}
      {prefix}
      {body}
      {suffix}
    </span>
  );
}
