import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { MotionConfig } from "motion/react";

import "./styles/tailwind.css";

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
