import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { MotionConfig } from "motion/react";

// Oat provides the base design layer: semantic HTML defaults, CSS-variable
// theming and automatic dark mode. Our tokens layer on top of it.
import "@knadh/oat/oat.min.css";
import "./styles/theme.css";
import "./styles/app.css";

import { App } from "./App";
import { StoreProvider } from "./state/store";

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    {/* reducedMotion="user" makes every motion component in the tree honour the
        OS setting by default; components additionally branch on useReducedMotion
        where an animation needs to be structurally different rather than just
        shorter. */}
    <MotionConfig reducedMotion="user">
      <StoreProvider>
        <App />
      </StoreProvider>
    </MotionConfig>
  </StrictMode>,
);
