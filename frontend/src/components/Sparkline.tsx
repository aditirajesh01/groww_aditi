import { motion, useReducedMotion } from "motion/react";
import { asOf, money } from "@/lib/format";

/**
 * Deliberately unadorned: no axes, no grid, no tooltip theatre. The dashed line
 * is the starting level, so the shape reads as "against where it began" rather
 * than as an abstract squiggle. The stroke draws in once, which makes the
 * left-to-right direction of time explicit.
 */
export function Sparkline({
  points,
  width = 640,
  height = 84,
}: {
  points: { t: string; c: number }[];
  width?: number;
  height?: number;
}) {
  const reduced = useReducedMotion();
  if (points.length < 2) return null;

  const values = points.map((p) => p.c);
  const min = Math.min(...values);
  const max = Math.max(...values);
  const span = max - min || 1;
  const pad = 6;

  const x = (i: number) => (i / (points.length - 1)) * width;
  const y = (v: number) => pad + (1 - (v - min) / span) * (height - pad * 2);

  const line = points.map((p, i) => `${i === 0 ? "M" : "L"}${x(i).toFixed(2)},${y(p.c).toFixed(2)}`).join(" ");
  const area = `${line} L${width},${height} L0,${height} Z`;
  const direction = values.at(-1)! > values[0] ? "up" : values.at(-1)! < values[0] ? "down" : "flat";
  const baseY = y(values[0]);

  return (
    <figure style={{ margin: 0 }}>
      <svg
        className="spark"
        data-direction={direction}
        viewBox={`0 0 ${width} ${height}`}
        preserveAspectRatio="none"
        role="img"
        aria-label={`Price path over ${points.length} sessions, from ₹${money(values[0])} to ₹${money(values.at(-1)!)}`}
      >
        <path className="spark__area" d={area} style={{ color: `var(--${direction === "down" ? "neg" : direction === "up" ? "pos" : "ink-3"})` }} />
        <line className="spark__base" x1="0" x2={width} y1={baseY} y2={baseY} />
        <motion.path
          className="spark__line"
          d={line}
          initial={reduced ? false : { pathLength: 0, opacity: 0.2 }}
          animate={{ pathLength: 1, opacity: 1 }}
          transition={reduced ? { duration: 0 } : { duration: 1.1, ease: [0.16, 1, 0.3, 1] }}
        />
      </svg>
      <figcaption className="eyebrow" style={{ marginTop: "0.4rem" }}>
        {asOf(points[0].t)} → {asOf(points.at(-1)!.t)} · dashed line is where it started
      </figcaption>
    </figure>
  );
}
