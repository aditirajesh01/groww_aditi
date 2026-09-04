import { motion, useReducedMotion } from "motion/react";
import { asOf, money } from "@/lib/format";

const STROKE: Record<string, string> = {
  up: "#12b76a",
  down: "#f04438",
  flat: "#98a2b3",
};

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
  const color = STROKE[direction];

  return (
    <figure className="m-0 rounded-2xl border border-gray-200 bg-white p-5 shadow-sm dark:border-gray-800 dark:bg-gray-900">
      <svg
        viewBox={`0 0 ${width} ${height}`}
        preserveAspectRatio="none"
        className="h-24 w-full"
        role="img"
        aria-label={`Price path over ${points.length} sessions, from ₹${money(values[0])} to ₹${money(values.at(-1)!)}`}
      >
        <path d={area} fill={color} opacity={0.08} />
        <line x1="0" x2={width} y1={baseY} y2={baseY} stroke="#d0d5dd" strokeDasharray="4 4" strokeWidth="1" />
        <motion.path
          d={line}
          fill="none"
          stroke={color}
          strokeWidth="2"
          strokeLinecap="round"
          strokeLinejoin="round"
          initial={reduced ? false : { pathLength: 0, opacity: 0.2 }}
          animate={{ pathLength: 1, opacity: 1 }}
          transition={reduced ? { duration: 0 } : { duration: 1.1, ease: [0.16, 1, 0.3, 1] }}
        />
      </svg>
      <figcaption className="mt-2 text-xs font-medium text-gray-400">
        {asOf(points[0].t)} → {asOf(points.at(-1)!.t)} · dashed line is where it started
      </figcaption>
    </figure>
  );
}
