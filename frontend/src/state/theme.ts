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

const media = () => window.matchMedia("(prefers-color-scheme: dark)");

/** Resolve "system" to the OS's actual current preference. Tailwind's `dark:`
 *  variant here is driven purely by `data-theme="dark"|"light"` (see
 *  tailwind.css's @custom-variant) so "system" has to be resolved to a real
 *  value up front, not left as an absent attribute for a media query to
 *  pick up — a hybrid selector-or-media dark variant isn't expressible as a
 *  single Tailwind custom variant. */
function apply(choice: ThemeChoice) {
  const root = document.documentElement;
  const resolved = choice === "system" ? (media().matches ? "dark" : "light") : choice;
  root.setAttribute("data-theme", resolved);
}

export function useTheme() {
  const [choice, setChoice] = useState<ThemeChoice>(read);

  useEffect(() => {
    apply(choice);
    try {
      localStorage.setItem(KEY, choice);
    } catch {
      /* not fatal */
    }

    if (choice !== "system") return;
    const mq = media();
    const onChange = () => apply("system");
    mq.addEventListener("change", onChange);
    return () => mq.removeEventListener("change", onChange);
  }, [choice]);

  const cycle = useCallback(() => {
    setChoice((c) => (c === "system" ? "light" : c === "light" ? "dark" : "system"));
  }, []);

  return { choice, setChoice, cycle };
}
