/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_USE_FIXTURES?: string;
  readonly VITE_API_BASE?: string;
  readonly VITE_FIXTURE_LATENCY_MS?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}

declare module "@contracts/fixtures/*.json" {
  const value: unknown;
  export default value;
}
