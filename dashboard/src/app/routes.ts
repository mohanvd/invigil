import { useSyncExternalStore } from "react"

export const PAGES = [
  { id: "live", title: "Live" },
  { id: "sessions", title: "Sessions" },
  { id: "results", title: "Results" },
  { id: "unit", title: "Unit" },
  { id: "settings", title: "Settings" },
] as const

export type PageId = (typeof PAGES)[number]["id"]

function pageFromHash(): PageId {
  const id = window.location.hash.replace(/^#\/?/, "")
  return PAGES.find((p) => p.id === id)?.id ?? "live"
}

function subscribe(listener: () => void): () => void {
  window.addEventListener("hashchange", listener)
  return () => window.removeEventListener("hashchange", listener)
}

/** The current page, from the URL hash (#/live, #/sessions, ...). */
export function usePage(): PageId {
  return useSyncExternalStore(subscribe, pageFromHash)
}

export function pageHref(id: PageId): string {
  return `#/${id}`
}
