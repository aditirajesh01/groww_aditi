import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";
import { fileURLToPath, URL } from "node:url";

// `../contracts` (a sibling of this directory, shared with the backend) is
// the real source of truth during development. It is also copied into
// `./contracts` so the frontend is a self-contained deployable unit -- a
// standalone host (Vercel et al.) only uploads this directory, and a repo-root
// build config to work around that turned out to be more fragile than a
// plain copy. Re-run `cp -r ../contracts ./contracts` after editing the
// shared contract; nothing here does that automatically.
const contracts = fileURLToPath(new URL("./contracts", import.meta.url));

export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: {
    alias: {
      "@contracts": contracts,
      "@": fileURLToPath(new URL("./src", import.meta.url)),
    },
  },
  server: {
    port: 5173,
    proxy: {
      // Only used when VITE_USE_FIXTURES=false and no absolute VITE_API_BASE is set.
      "/api": { target: "http://localhost:8000", changeOrigin: true },
    },
  },
});
