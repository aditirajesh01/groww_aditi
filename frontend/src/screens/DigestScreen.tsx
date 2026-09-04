import { useCallback, useState } from "react";
import { AnimatePresence, motion, useReducedMotion } from "motion/react";
import type { ChangeItem, SignalKind } from "@/api/types";
import { ChangeCard } from "@/components/ChangeCard";
import { DigestHeader } from "@/components/DigestHeader";
import { InboxZero } from "@/components/InboxZero";
import { QuietList } from "@/components/QuietList";
import { DigestSkeleton } from "@/components/Skeleton";
import { cardVariants, listVariants, spring, type ExitMode } from "@/lib/motion";
import { useStore } from "@/state/store";

export function DigestScreen() {
  const store = useStore();
  const reduced = useReducedMotion();
  const [exitMode, setExitMode] = useState<ExitMode>("read");

  const onAck = useCallback(
    (item: ChangeItem) => {
      setExitMode("read");
      void store.ack(item);
    },
    [store],
  );

  const onDismiss = useCallback(
    (item: ChangeItem, kind: SignalKind) => {
      setExitMode("dismissed");
      void store.dismiss(item, kind);
    },
    [store],
  );

  if (store.status === "loading" && !store.digest) return <DigestSkeleton />;

  if (store.status === "error") {
    return (
      <div className="mx-auto max-w-5xl px-6 py-8">
        <div className="rounded-2xl border border-error-200 bg-error-50 p-6 dark:border-error-500/30 dark:bg-error-500/10">
          <p className="text-sm text-error-700 dark:text-error-400">
            Could not reach the digest service: {store.error}
          </p>
          <button
            type="button"
            onClick={() => void store.refresh()}
            className="mt-3 rounded-lg bg-brand-500 px-4 py-2 text-sm font-semibold text-white hover:bg-brand-600"
          >
            Try again
          </button>
        </div>
      </div>
    );
  }

  const digest = store.digest;
  if (!digest) return null;

  const thesisFor = (symbol: string) =>
    store.watchlist?.entries.find((e) => e.symbol === symbol)?.thesis_added_at ?? null;

  const variants = cardVariants(!!reduced);

  return (
    <div className="mx-auto flex max-w-5xl flex-col gap-6 px-6 py-8">
      <DigestHeader
        digest={digest}
        shown={store.items.length}
        suppressed={store.budget.suppressed}
        quietCount={digest.quiet.length}
        cleared={store.cleared}
      />

      <AnimatePresence initial={false}>
        {store.corrections.length > 0 && (
          <motion.section
            key="corrections"
            layout={!reduced}
            exit={{ opacity: 0, height: 0, marginTop: 0 }}
            style={{ overflow: "hidden" }}
          >
            <h2 className="mb-3 text-lg font-bold text-warning-600 dark:text-warning-400">Corrections</h2>
            <ul className="flex flex-col gap-4">
              <AnimatePresence initial={false} custom={exitMode}>
                {store.corrections.map((item, i) => (
                  <motion.li
                    key={item.event_id}
                    layout={!reduced}
                    custom={exitMode}
                    variants={variants}
                    initial="hidden"
                    animate="shown"
                    exit="gone"
                    transition={reduced ? { duration: 0 } : spring}
                  >
                    <ChangeCard item={item} rank={i + 1} onAck={onAck} />
                  </motion.li>
                ))}
              </AnimatePresence>
            </ul>
          </motion.section>
        )}
      </AnimatePresence>

      <section>
        {store.items.length > 0 && (
          <div className="mb-3 flex items-center gap-3">
            <h2 className="text-lg font-bold text-gray-800 dark:text-white">Ranked by attention</h2>
            {store.items.length > 1 && (
              <button
                type="button"
                onClick={() => {
                  setExitMode("read");
                  void store.ackAll();
                }}
                className="ml-auto rounded-lg border border-gray-200 px-3 py-1.5 text-xs font-semibold text-gray-600 hover:bg-gray-50 dark:border-gray-700 dark:text-gray-300 dark:hover:bg-white/5"
              >
                Mark all read
              </button>
            )}
          </div>
        )}

        {store.inboxZero ? (
          <InboxZero
            cleared={store.cleared}
            suppressed={store.budget.suppressed}
            quiet={digest.quiet.length}
            onRefresh={() => void store.refresh()}
            onAdvance={(h) => void store.advanceSim(h)}
            canAdvance={store.mode === "fixtures"}
            busy={store.busy || store.status === "loading"}
          />
        ) : (
          <motion.ul className="flex flex-col gap-4" variants={listVariants(!!reduced)} initial="hidden" animate="shown">
            <AnimatePresence initial={false} custom={exitMode} mode="popLayout">
              {store.items.map((item, i) => (
                <motion.li
                  key={item.event_id}
                  layout={!reduced}
                  custom={exitMode}
                  variants={variants}
                  exit="gone"
                  transition={reduced ? { duration: 0 } : spring}
                >
                  <ChangeCard
                    item={item}
                    rank={i + 1}
                    thesisAddedAt={thesisFor(item.symbol)}
                    onAck={onAck}
                    onDismiss={onDismiss}
                  />
                </motion.li>
              ))}
            </AnimatePresence>
          </motion.ul>
        )}
      </section>

      {digest.quiet.length > 0 && <QuietList items={digest.quiet} checkedAt={digest.generated_at} />}
    </div>
  );
}
