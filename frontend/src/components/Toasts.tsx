import { AnimatePresence, motion, useReducedMotion } from "motion/react";
import type { Toast } from "@/state/store";

export function Toasts({
  toasts,
  onDismiss,
}: {
  toasts: Toast[];
  onDismiss: (id: number) => void;
}) {
  const reduced = useReducedMotion();
  return (
    <div className="toasts" role="status" aria-live="polite">
      <AnimatePresence initial={false}>
        {toasts.map((t) => (
          <motion.div
            key={t.id}
            className="toast"
            data-tone={t.tone}
            layout={!reduced}
            initial={reduced ? false : { opacity: 0, y: 16, scale: 0.97 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={reduced ? { opacity: 0 } : { opacity: 0, y: 8, scale: 0.97 }}
            transition={reduced ? { duration: 0 } : { duration: 0.28, ease: [0.16, 1, 0.3, 1] }}
          >
            <span className="toast__text">
              {t.text}
              {t.detail && <span className="toast__detail">{t.detail}</span>}
            </span>
            {t.undo && (
              <button
                type="button"
                className="btn btn--sm"
                onClick={() => {
                  t.undo?.();
                  onDismiss(t.id);
                }}
              >
                Undo
              </button>
            )}
            <button
              type="button"
              className="icon-btn"
              aria-label="Dismiss notification"
              onClick={() => onDismiss(t.id)}
            >
              ✕
            </button>
          </motion.div>
        ))}
      </AnimatePresence>
    </div>
  );
}
