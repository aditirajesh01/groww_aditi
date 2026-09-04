import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import { fileURLToPath, URL } from "node:url";

// The contracts directory lives OUTSIDE the frontend root. It is the single
// source of truth shared with the backend, so we alias into it rather than
// copying (a copy would be free to drift, which is exactly what we must not do).
const contracts = fileURLToPath(new URL("../contracts", import.meta.url));

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      "@contracts": contracts,
      "@": fileURLToPath(new URL("./src", import.meta.url)),
    },
  },
  server: {
    port: 5173,
    // Allow the dev server to read ../contracts/fixtures/*.json
    fs: { allow: [fileURLToPath(new URL("..", import.meta.url))] },
    proxy: {
      // Only used when VITE_USE_FIXTURES=false and no absolute VITE_API_BASE is set.
      "/api": { target: "http://localhost:8000", changeOrigin: true },
    },
  },
});
