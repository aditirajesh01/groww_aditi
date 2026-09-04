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
    <div
      role="status"
      aria-live="polite"
      className="pointer-events-none fixed inset-x-0 bottom-4 z-50 flex flex-col items-center gap-2 px-4 sm:items-end sm:right-4 sm:left-auto"
    >
      <AnimatePresence initial={false}>
        {toasts.map((t) => (
          <motion.div
            key={t.id}
            layout={!reduced}
            initial={reduced ? false : { opacity: 0, y: 16, scale: 0.97 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={reduced ? { opacity: 0 } : { opacity: 0, y: 8, scale: 0.97 }}
            transition={reduced ? { duration: 0 } : { duration: 0.28, ease: [0.16, 1, 0.3, 1] }}
            className={
              "pointer-events-auto flex w-full max-w-sm items-start gap-3 rounded-xl border px-4 py-3 shadow-lg " +
              (t.tone === "warn"
                ? "border-error-200 bg-white dark:border-error-500/30 dark:bg-gray-900"
                : "border-gray-200 bg-white dark:border-gray-700 dark:bg-gray-900")
            }
          >
            <span className="min-w-0 flex-1 text-sm text-gray-700 dark:text-gray-200">
              {t.text}
              {t.detail && <span className="mt-0.5 block text-xs text-gray-400">{t.detail}</span>}
            </span>
            {t.undo && (
              <button
                type="button"
                onClick={() => {
                  t.undo?.();
                  onDismiss(t.id);
                }}
                className="flex-none text-sm font-semibold text-brand-600 hover:text-brand-700 dark:text-brand-400"
              >
                Undo
              </button>
            )}
            <button
              type="button"
              aria-label="Dismiss notification"
              onClick={() => onDismiss(t.id)}
              className="flex-none text-gray-300 hover:text-gray-500 dark:hover:text-gray-300"
            >
              ✕
            </button>
          </motion.div>
        ))}
      </AnimatePresence>
    </div>
  );
}
