import type { ReactElement } from "react";
import { href, useRoute } from "@/state/router";
import { useStore } from "@/state/store";

const ICONS: Record<string, ReactElement> = {
  digest: (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8">
      <path d="M4 6h16M4 12h10M4 18h13" strokeLinecap="round" />
      <circle cx="19.5" cy="12" r="1.4" fill="currentColor" stroke="none" />
    </svg>
  ),
  watchlist: (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8">
      <path d="M3 12s3.5-7 9-7 9 7 9 7-3.5 7-9 7-9-7-9-7Z" strokeLinejoin="round" />
      <circle cx="12" cy="12" r="2.6" />
    </svg>
  ),
  system: (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8">
      <rect x="3.5" y="4" width="17" height="12" rx="1.6" />
      <path d="M8 20h8M12 16v4" strokeLinecap="round" />
    </svg>
  ),
};

const ITEMS: { name: "digest" | "watchlist" | "system"; label: string }[] = [
  { name: "digest", label: "Digest" },
  { name: "watchlist", label: "Watchlist" },
  { name: "system", label: "System" },
];

export function Sidebar() {
  const { route } = useRoute();
  const store = useStore();

  return (
    <aside className="sidebar">
      <a className="sidebar__brand" href={href({ name: "digest" })}>
        <span className="sidebar__mark" aria-hidden="true">
          <svg width="22" height="22" viewBox="0 0 24 24" fill="none">
            <rect x="2" y="2" width="20" height="20" rx="6" fill="var(--brand)" />
            <path d="M7 14.5 10.5 10l3 3.2L17 8.5" stroke="white" strokeWidth="1.8"
              strokeLinecap="round" strokeLinejoin="round" fill="none" />
          </svg>
        </span>
        <span className="sidebar__brand-text">
          Watchlist
          <small>changelog · read cursor</small>
        </span>
      </a>

      <nav className="sidebar__nav" aria-label="Primary">
        <span className="sidebar__section">Menu</span>
        {ITEMS.map((item) => {
          const active = route.name === item.name;
          return (
            <a
              key={item.name}
              href={href({ name: item.name })}
              className="sidebar__link"
              data-active={active || undefined}
            >
              <span className="sidebar__icon">{ICONS[item.name]}</span>
              {item.label}
              {item.name === "digest" && store.unread > 0 && (
                <span className="sidebar__badge">{store.unread}</span>
              )}
            </a>
          );
        })}
      </nav>

      <div className="sidebar__foot">
        <span className="sidebar__mode">{store.mode === "fixtures" ? "Fixture data" : "Live API"}</span>
        <span className="sidebar__foot-note">No recommendations. Every claim is evidence-linked.</span>
      </div>
    </aside>
  );
}
