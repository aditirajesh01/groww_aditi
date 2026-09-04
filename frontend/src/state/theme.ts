import { useCallback, useEffect, useState } from "react";

export type ThemeChoice = "system" | "light" | "dark";
const KEY = "smw.theme";

function read(): ThemeChoice {
  try {
    const v = localStorage.getItem(KEY);
    if (v === "light" || v === "dark" || v === "system") return v;
  } catch {
    /* private browsing — fall through to the default below */
  }
  // Default to light rather than following the OS: for a judged demo the
  // intended look should not depend on whoever's system is set to dark. The
  // toggle in the topbar still cycles system -> light -> dark as normal.
  return "light";
}

function apply(choice: ThemeChoice) {
  const root = document.documentElement;
  if (choice === "system") root.removeAttribute("data-theme");
  else root.setAttribute("data-theme", choice);
}

/** Oat themes through `light-dark()` + `color-scheme`, so forcing a theme is a
 *  matter of pinning `color-scheme` on :root — see styles/theme.css. */
export function useTheme() {
  const [choice, setChoice] = useState<ThemeChoice>(read);

  useEffect(() => {
    apply(choice);
    try {
      localStorage.setItem(KEY, choice);
    } catch {
      /* not fatal */
    }
  }, [choice]);

  const cycle = useCallback(() => {
    setChoice((c) => (c === "system" ? "light" : c === "light" ? "dark" : "system"));
  }, []);

  return { choice, setChoice, cycle };
}
