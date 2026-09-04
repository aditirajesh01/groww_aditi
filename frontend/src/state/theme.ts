import { useCallback, useEffect, useState } from "react";

export type ThemeChoice = "system" | "light" | "dark";
const KEY = "smw.theme";

function read(): ThemeChoice {
  try {
    const v = localStorage.getItem(KEY);
    if (v === "light" || v === "dark" || v === "system") return v;
  } catch {
    /* private browsing — fall through to system */
  }
  return "system";
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
