import type { SourceKind } from "@/data/types"

// Build flags. The public site is built with VITE_DEMO_ONLY=true: it has no
// broker to reach, so it always shows Demo and hides everything about Live.

export const SITE_URL = "https://invigil.xyz"
export const REPO_URL = "https://github.com/mohanvd/invigil"

/** Only the exact string "true" turns the flag on. Unset, empty or anything else is off. */
export function isDemoOnly(env: { VITE_DEMO_ONLY?: string } = import.meta.env): boolean {
  return env.VITE_DEMO_ONLY === "true"
}

/** The source to run: the one chosen in Settings, unless the build is demo only. */
export function effectiveSource(chosen: SourceKind, demoOnly: boolean): SourceKind {
  return demoOnly ? "demo" : chosen
}

export const DEMO_ONLY = isDemoOnly()
