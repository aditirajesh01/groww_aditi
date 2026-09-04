import { AnimatePresence, motion, useReducedMotion } from "motion/react";
import { Toasts } from "@/components/Toasts";
import { DigestScreen } from "@/screens/DigestScreen";
import { SymbolScreen } from "@/screens/SymbolScreen";
import { SystemScreen } from "@/screens/SystemScreen";
import { WatchlistScreen } from "@/screens/WatchlistScreen";
import { href, useRoute } from "@/state/router";
import { useStore } from "@/state/store";
import { useTheme } from "@/state/theme";

const THEME_GLYPH = { system: "◐", light: "☀", dark: "☾" } as const;
const THEME_LABEL = {
  system: "Theme: following your system",
  light: "Theme: light",
  dark: "Theme: dark",
} as const;

export function App() {
  const { route } = useRoute();
  const store = useStore();
  const { choice, cycle } = useTheme();
  const reduced = useReducedMotion();

  const key =
    route.name === "symbol" ? `symbol:${route.symbol}` : route.name;

  return (
    <div className="shell">
      <a href="#main" className="visually-hidden">
        Skip to content
      </a>

      <header className="topbar">
        <div className="wrap topbar__inner">
          <a className="brand" href={href({ name: "digest" })}>
            <span className="brand__mark">Watchlist</span>
            <span className="brand__sub">a changelog with a read cursor</span>
          </a>

          <nav className="nav" aria-label="Primary">
            <a href={href({ name: "digest" })} aria-current={route.name === "digest" ? "page" : undefined}>
              Digest
              {store.unread > 0 && <span className="pill-count">{store.unread}</span>}
            </a>
            <a
              href={href({ name: "watchlist" })}
              aria-current={route.name === "watchlist" ? "page" : undefined}
            >
              Watchlist
            </a>
            <a href={href({ name: "system" })} aria-current={route.name === "system" ? "page" : undefined}>
              System
            </a>
          </nav>

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

      <footer className="foot">
        <div className="wrap" style={{ display: "flex", gap: "var(--space-4)", flexWrap: "wrap", alignItems: "center" }}>
          <span className="mode-tag">
            {store.mode === "fixtures" ? "fixture data" : "live api"}
          </span>
          <p className="foot__note" style={{ margin: 0 }}>
            No recommendations, targets, or buy/sell language anywhere in this product. Every claim
            on a card traces to dated evidence you can open.
          </p>
        </div>
      </footer>

      <Toasts toasts={store.toasts} onDismiss={store.dismissToast} />
    </div>
  );
}
