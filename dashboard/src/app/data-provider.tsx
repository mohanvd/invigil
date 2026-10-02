import { useEffect, useMemo, useState } from "react"
import type { ReactNode } from "react"

import { createDemoSource } from "@/data/demo-source"
import { createLiveSource } from "@/data/live-source"
import { createHallStore } from "@/data/store"

import { DataContext } from "./data"
import { useSettings } from "./settings"

export function DataProvider({ children }: { children: ReactNode }) {
  const { settings, password } = useSettings()
  const [store] = useState(() => createHallStore())

  const source = useMemo(
    () =>
      settings.source === "live"
        ? createLiveSource({ url: settings.brokerUrl, username: settings.username, password })
        : createDemoSource(),
    [settings.source, settings.brokerUrl, settings.username, password]
  )

  useEffect(() => {
    store.reset()
    source.start(store)
    store.flush()
    return () => source.stop()
  }, [store, source])

  const value = useMemo(() => ({ store, source }), [store, source])

  return <DataContext.Provider value={value}>{children}</DataContext.Provider>
}
