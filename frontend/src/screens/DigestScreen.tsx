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
      <div className="wrap section">
        <div className="empty-note">
          <p style={{ margin: 0 }}>
            Could not reach the digest service: {store.error}
          </p>
          <button type="button" className="btn" style={{ marginTop: "1rem" }} onClick={() => void store.refresh()}>
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
    <>
      <div className="wrap">
        <DigestHeader
          digest={digest}
          shown={store.items.length}
          suppressed={store.budget.suppressed}
          quietCount={digest.quiet.length}
          cleared={store.cleared}
        />
      </div>

      {/* Corrections come first. An admission that we showed a wrong number
          outranks anything we would like to tell you today. */}
      <AnimatePresence initial={false}>
        {store.corrections.length > 0 && (
          <motion.section
            className="wrap section"
            key="corrections"
            layout={!reduced}
            exit={{ opacity: 0, height: 0, paddingBlock: 0 }}
            style={{ overflow: "hidden" }}
          >
            <div className="section__head">
              <h2 className="section__title" style={{ color: "var(--brass)" }}>
                Corrections
              </h2>
            </div>
            <ul className="stack">
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

      <section className="wrap section">
        {store.items.length > 0 && (
          <div className="section__head">
            <h2 className="section__title">Ranked by attention</h2>
            {store.items.length > 1 && (
              <button
                type="button"
                className="btn btn--ghost btn--sm"
                style={{ marginInlineStart: "auto" }}
                onClick={() => {
                  setExitMode("read");
                  void store.ackAll();
                }}
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
          <motion.ul
            className="stack"
            variants={listVariants(!!reduced)}
            initial="hidden"
            animate="shown"
          >
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

      {digest.quiet.length > 0 && (
        <section className="wrap section">
          <QuietList items={digest.quiet} checkedAt={digest.generated_at} />
        </section>
      )}
    </>
  );
}
