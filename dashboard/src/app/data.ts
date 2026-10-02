import { createContext, useContext, useEffect, useState, useSyncExternalStore } from "react"

import type { HallStore } from "@/data/store"
import type { DataSource, HallState } from "@/data/types"

export interface DataContextValue {
  store: HallStore
  source: DataSource
}

export const DataContext = createContext<DataContextValue | null>(null)

export function useData(): DataContextValue {
  const value = useContext(DataContext)
  if (!value) throw new Error("useData must be used inside DataProvider")
  return value
}

/** The live state of the hall. Re-renders at most a few times per second. */
export function useHall(): HallState {
  const { store } = useData()
  return useSyncExternalStore(store.subscribe, store.getSnapshot)
}

/** The current time, refreshed on an interval, for "3 s ago" and online checks. */
export function useNow(everyMs = 1000): number {
  const [now, setNow] = useState(Date.now)
  useEffect(() => {
    const timer = setInterval(() => setNow(Date.now()), everyMs)
    return () => clearInterval(timer)
  }, [everyMs])
  return now
}

export type Loadable<T> = { status: "loading" } | { status: "ready"; value: T }

/** Load something from the current source, and again whenever the source changes. */
export function useSourceQuery<T>(load: (source: DataSource) => Promise<T>): Loadable<T> {
  const { source } = useData()
  const [result, setResult] = useState<{ source: DataSource; value: T } | null>(null)

  useEffect(() => {
    let cancelled = false
    load(source).then((value) => {
      if (!cancelled) setResult({ source, value })
    })
    return () => {
      cancelled = true
    }
  }, [source, load])

  if (result === null || result.source !== source) return { status: "loading" }
  return { status: "ready", value: result.value }
}
