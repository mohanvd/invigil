/// <reference types="vite/client" />

interface ImportMetaEnv {
  /** "true" builds the public demo: Demo source only, no broker settings. */
  readonly VITE_DEMO_ONLY?: string
}

interface ImportMeta {
  readonly env: ImportMetaEnv
}
