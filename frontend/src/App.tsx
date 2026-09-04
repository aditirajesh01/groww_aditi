import { AnimatePresence, motion, useReducedMotion } from "motion/react";
import { Sidebar } from "@/components/Sidebar";
import { Toasts } from "@/components/Toasts";
import { DigestScreen } from "@/screens/DigestScreen";
import { SymbolScreen } from "@/screens/SymbolScreen";
import { SystemScreen } from "@/screens/SystemScreen";
import { WatchlistScreen } from "@/screens/WatchlistScreen";
import { useRoute } from "@/state/router";
import { useStore } from "@/state/store";
import { useTheme } from "@/state/theme";

const THEME_GLYPH = { system: "◐", light: "☀", dark: "☾" } as const;
const THEME_LABEL = {
  system: "Theme: following your system",
  light: "Theme: light",
  dark: "Theme: dark",
} as const;

const TITLES: Record<string, string> = {
  digest: "Digest",
  watchlist: "Watchlist",
  system: "System",
  symbol: "Symbol",
};

export function App() {
  const { route } = useRoute();
  const store = useStore();
  const { choice, cycle } = useTheme();
  const reduced = useReducedMotion();

  const key = route.name === "symbol" ? `symbol:${route.symbol}` : route.name;

  return (
    <div className="flex min-h-dvh bg-gray-50 dark:bg-gray-950">
      <a href="#main" className="sr-only focus:not-sr-only">
        Skip to content
      </a>

      <Sidebar />

      <div className="flex min-w-0 flex-1 flex-col">
        <header className="sticky top-0 z-40 flex h-16 flex-none items-center justify-between border-b border-gray-200 bg-white/80 px-6 backdrop-blur dark:border-gray-800 dark:bg-gray-900/80">
          <h1 className="text-lg font-bold text-gray-800 dark:text-white">{TITLES[route.name]}</h1>
          <button
            type="button"
            onClick={cycle}
            title={THEME_LABEL[choice]}
            aria-label={THEME_LABEL[choice]}
            className="grid h-9 w-9 place-items-center rounded-lg border border-gray-200 text-gray-500 transition-colors hover:bg-gray-50 hover:text-gray-800 dark:border-gray-700 dark:text-gray-400 dark:hover:bg-white/5 dark:hover:text-white"
          >
            {THEME_GLYPH[choice]}
          </button>
        </header>

        <main id="main" className="flex-1">
          <AnimatePresence mode="wait" initial={false}>
            <motion.div
              key={key}
              initial={reduced ? false : { opacity: 0, y: 6 }}
              animate={{ opacity: 1, y: 0 }}
              exit={reduced ? { opacity: 0 } : { opacity: 0, y: -4 }}
              transition={reduced ? { duration: 0 } : { duration: 0.22, ease: [0.16, 1, 0.3, 1] }}
            >
              {route.name === "digest" && <DigestScreen />}
              {route.name === "watchlist" && <WatchlistScreen />}
              {route.name === "system" && <SystemScreen />}
              {route.name === "symbol" && <SymbolScreen symbol={route.symbol} />}
            </motion.div>
          </AnimatePresence>
        </main>
      </div>

      <Toasts toasts={store.toasts} onDismiss={store.dismissToast} />
    </div>
  );
}
