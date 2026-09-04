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

  const key =
    route.name === "symbol" ? `symbol:${route.symbol}` : route.name;

  return (
    <div className="shell shell--sidebar">
      <a href="#main" className="visually-hidden">
        Skip to content
      </a>

      <Sidebar />

      <div className="shell__body">
        <header className="topbar topbar--slim">
          <div className="topbar__inner">
            <span className="topbar__crumb">{TITLES[route.name]}</span>
            <button
              type="button"
              className="icon-btn"
              onClick={cycle}
              title={THEME_LABEL[choice]}
              aria-label={THEME_LABEL[choice]}
            >
              {THEME_GLYPH[choice]}
            </button>
          </div>
        </header>

        <main id="main">
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
