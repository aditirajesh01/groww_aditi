import { useCallback, useEffect, useState } from "react";

export type Route =
  | { name: "digest" }
  | { name: "watchlist" }
  | { name: "symbol"; symbol: string }
  | { name: "system" };

function parse(hash: string): Route {
  const path = hash.replace(/^#\/?/, "");
  if (path.startsWith("s/")) return { name: "symbol", symbol: decodeURIComponent(path.slice(2)) };
  if (path === "watchlist") return { name: "watchlist" };
  if (path === "system") return { name: "system" };
  return { name: "digest" };
}

export const href = (route: Route): string =>
  route.name === "symbol"
    ? `#/s/${encodeURIComponent(route.symbol)}`
    : route.name === "digest"
      ? "#/"
      : `#/${route.name}`;

/** Hash routing: no dependency, no server config, and the back button works. */
export function useRoute() {
  const [route, setRoute] = useState<Route>(() => parse(window.location.hash));

  useEffect(() => {
    const onChange = () => {
      setRoute(parse(window.location.hash));
      window.scrollTo({ top: 0, behavior: "instant" as ScrollBehavior });
    };
    window.addEventListener("hashchange", onChange);
    return () => window.removeEventListener("hashchange", onChange);
  }, []);

  const navigate = useCallback((next: Route) => {
    window.location.hash = href(next);
  }, []);

  return { route, navigate };
}
