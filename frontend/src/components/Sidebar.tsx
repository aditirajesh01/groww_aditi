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
    <aside className="flex h-dvh w-[290px] flex-none flex-col border-r border-gray-200 bg-white px-5 py-6 dark:border-gray-800 dark:bg-gray-900">
      <a href={href({ name: "digest" })} className="flex items-center gap-2.5 px-1">
        <span className="grid h-9 w-9 flex-none place-items-center rounded-xl bg-brand-500 text-white shadow-sm shadow-brand-500/30">
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none">
            <path d="M7 14.5 10.5 10l3 3.2L17 8.5" stroke="white" strokeWidth="2"
              strokeLinecap="round" strokeLinejoin="round" fill="none" />
          </svg>
        </span>
        <span className="flex flex-col leading-tight">
          <span className="text-base font-bold tracking-tight text-gray-800 dark:text-white">Watchlist</span>
          <span className="text-[11px] font-medium uppercase tracking-wide text-gray-400">Changelog · Read Cursor</span>
        </span>
      </a>

      <nav aria-label="Primary" className="mt-8 flex flex-col gap-1">
        <span className="mb-1 px-3 text-xs font-semibold uppercase tracking-wider text-gray-400">Menu</span>
        {ITEMS.map((item) => {
          const active = route.name === item.name;
          return (
            <a
              key={item.name}
              href={href({ name: item.name })}
              className={
                "group flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium transition-colors " +
                (active
                  ? "bg-brand-50 text-brand-600 dark:bg-brand-500/15 dark:text-brand-400"
                  : "text-gray-500 hover:bg-gray-50 hover:text-gray-800 dark:text-gray-400 dark:hover:bg-white/5 dark:hover:text-white")
              }
            >
              <span className={active ? "text-brand-500" : "text-gray-400 group-hover:text-gray-500"}>
                {ICONS[item.name]}
              </span>
              {item.label}
              {item.name === "digest" && store.unread > 0 && (
                <span className="ml-auto grid h-5 min-w-5 place-items-center rounded-full bg-brand-500 px-1.5 text-[11px] font-bold text-white">
                  {store.unread}
                </span>
              )}
            </a>
          );
        })}
      </nav>
    </aside>
  );
}
