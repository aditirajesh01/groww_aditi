import { useEffect, useState } from "react";
import {
  AnimatePresence,
  motion,
  useMotionValue,
  useReducedMotion,
  useTransform,
  type PanInfo,
} from "motion/react";
import { getClient } from "@/api/client";
import type { DiscoverCard } from "@/api/types";
import { Ticker } from "./Ticker";

const DELTA_TONE: Record<string, string> = {
  up: "text-success-600 dark:text-success-400",
  down: "text-error-600 dark:text-error-400",
  neutral: "text-gray-400",
};
const toneOf = (n: number) => DELTA_TONE[n > 0 ? "up" : n < 0 ? "down" : "neutral"];

/**
 * Discovery as a card stack you swipe through, rather than a search box you
 * have to already know what to type into. The ranking signal is deliberately
 * arithmetic -- shared-sector count over total watched -- not a similarity
 * model, so "why is this card here" is answerable by reading the ratio on it.
 */
export function Discover({ onAdd }: { onAdd: (symbol: string) => Promise<void> }) {
  const reduced = useReducedMotion();
  const [cards, setCards] = useState<DiscoverCard[] | null>(null);
  const [index, setIndex] = useState(0);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    let live = true;
    void (async () => {
      const api = await getClient();
      const hits = await api.discover();
      if (live) {
        setCards(hits);
        setIndex(0);
      }
    })();
    return () => {
      live = false;
    };
  }, []);

  const current = cards?.[index];
  const next = cards?.[index + 1];

  async function decide(direction: "add" | "skip") {
    if (!current || busy) return;
    if (direction === "add") {
      setBusy(true);
      try {
        await onAdd(current.symbol);
      } finally {
        setBusy(false);
      }
    }
    setIndex((i) => i + 1);
  }

  if (cards === null) {
    return (
      <div className="flex h-72 items-center justify-center rounded-2xl border border-gray-200 bg-white dark:border-gray-800 dark:bg-gray-900">
        <div className="h-8 w-8 animate-spin rounded-full border-2 border-gray-200 border-t-brand-500 dark:border-gray-700" />
      </div>
    );
  }

  if (!current) {
    return (
      <div className="flex flex-col items-center gap-2 rounded-2xl border border-dashed border-gray-300 p-10 text-center dark:border-gray-700">
        <p className="text-sm font-medium text-gray-500 dark:text-gray-400">
          That&rsquo;s everything worth surfacing right now.
        </p>
        <p className="text-xs text-gray-400">Add a thesis to more watches and better matches will show up here.</p>
      </div>
    );
  }

  return (
    <div className="flex flex-col items-center gap-4">
      <div className="relative h-80 w-full max-w-sm">
        {next && (
          <div className="absolute inset-0 scale-[0.96] rounded-2xl border border-gray-200 bg-white opacity-60 dark:border-gray-800 dark:bg-gray-900" />
        )}
        <AnimatePresence initial={false}>
          <SwipeCard key={current.symbol} card={current} reduced={!!reduced} busy={busy} onDecide={decide} />
        </AnimatePresence>
      </div>

      <div className="flex items-center gap-4">
        <button
          type="button"
          onClick={() => void decide("skip")}
          disabled={busy}
          aria-label={`Skip ${current.symbol}`}
          className="grid h-12 w-12 place-items-center rounded-full border border-gray-200 text-gray-400 shadow-sm transition hover:border-error-300 hover:text-error-500 disabled:opacity-50 dark:border-gray-700"
        >
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
            <path d="M6 6l12 12M18 6L6 18" />
          </svg>
        </button>
        <span className="text-xs text-gray-400">
          {index + 1} / {cards.length}
        </span>
        <button
          type="button"
          onClick={() => void decide("add")}
          disabled={busy}
          aria-label={`Add ${current.symbol} to your watchlist`}
          className="grid h-12 w-12 place-items-center rounded-full border border-gray-200 text-gray-400 shadow-sm transition hover:border-success-300 hover:text-success-500 disabled:opacity-50 dark:border-gray-700"
        >
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
            <path d="M20 6L9 17l-5-5" />
          </svg>
        </button>
      </div>
    </div>
  );
}

function SwipeCard({
  card,
  reduced,
  busy,
  onDecide,
}: {
  card: DiscoverCard;
  reduced: boolean;
  busy: boolean;
  onDecide: (direction: "add" | "skip") => void;
}) {
  const x = useMotionValue(0);
  const rotate = useTransform(x, [-220, 0, 220], [-10, 0, 10]);
  const addOpacity = useTransform(x, [10, 120], [0, 1]);
  const skipOpacity = useTransform(x, [-120, -10], [1, 0]);

  function handleDragEnd(_: unknown, info: PanInfo) {
    const far = Math.abs(info.offset.x) > 110;
    const fast = Math.abs(info.velocity.x) > 500;
    if (!far && !fast) return;
    onDecide(info.offset.x > 0 ? "add" : "skip");
  }

  const pct = card.price.change_pct;

  return (
    <motion.div
      className="absolute inset-0 flex cursor-grab flex-col overflow-hidden rounded-2xl border border-gray-200 bg-white p-6 shadow-lg active:cursor-grabbing dark:border-gray-800 dark:bg-gray-900"
      style={{ x, rotate }}
      drag={reduced || busy ? false : "x"}
      dragConstraints={{ left: 0, right: 0 }}
      dragElastic={0.6}
      onDragEnd={handleDragEnd}
      initial={reduced ? false : { scale: 0.94, opacity: 0 }}
      animate={{ scale: 1, opacity: 1 }}
      exit={reduced ? { opacity: 0 } : { x: x.get() > 0 ? 300 : -300, opacity: 0, transition: { duration: 0.25 } }}
      transition={{ type: "spring", stiffness: 380, damping: 30 }}
    >
      <motion.span
        style={{ opacity: addOpacity }}
        className="pointer-events-none absolute right-5 top-5 rounded-md border-2 border-success-500 px-2 py-0.5 text-sm font-extrabold uppercase tracking-wide text-success-500"
      >
        Add
      </motion.span>
      <motion.span
        style={{ opacity: skipOpacity }}
        className="pointer-events-none absolute left-5 top-5 rounded-md border-2 border-error-500 px-2 py-0.5 text-sm font-extrabold uppercase tracking-wide text-error-500"
      >
        Skip
      </motion.span>

      <span className="w-fit rounded-full bg-gray-100 px-2.5 py-1 text-xs font-semibold text-gray-500 dark:bg-white/5 dark:text-gray-400">
        {card.sector}
      </span>

      <div className="mt-4">
        <div className="font-mono text-lg font-bold text-gray-800 dark:text-white">{card.symbol}</div>
        <div className="text-sm text-gray-400">{card.name}</div>
      </div>

      <div className="mt-6 font-mono text-3xl font-bold tabular-nums text-gray-800 dark:text-white">
        <span className="mr-1 text-xl font-semibold text-gray-400">₹</span>
        <Ticker value={card.price.last} grouped />
      </div>
      <div className={`mt-1 font-mono text-sm font-semibold ${toneOf(pct)}`}>
        <Ticker value={pct} signed suffix="%" /> today
      </div>

      <div className="mt-auto pt-6">
        <div className="flex items-baseline justify-between text-xs">
          <span className="font-medium text-gray-500 dark:text-gray-400">Sector match</span>
          <span className="font-mono font-semibold text-gray-700 dark:text-gray-200">
            {card.match.shared} / {card.match.total}
          </span>
        </div>
        <div className="mt-1.5 h-1.5 w-full overflow-hidden rounded-full bg-gray-100 dark:bg-gray-800">
          <div
            className="h-full rounded-full bg-brand-500"
            style={{ width: `${Math.round(card.match.ratio * 100)}%` }}
          />
        </div>
        <p className="mt-2 text-xs text-gray-400">
          {card.match.shared} of the {card.match.total} {card.match.total === 1 ? "symbol" : "symbols"} you
          watch {card.match.total === 1 ? "is" : "are"} in {card.sector}.
        </p>
      </div>
    </motion.div>
  );
}
