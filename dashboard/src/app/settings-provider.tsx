import { useMemo, useState } from "react"
import type { ReactNode } from "react"

import { writeJson, writeString } from "@/lib/storage"

import {
  DEFAULT_SETTINGS,
  PASSWORD_KEY,
  SETTINGS_KEY,
  SettingsContext,
  loadPassword,
  loadSettings,
} from "./settings"
import type { Settings, SettingsContextValue } from "./settings"

export function SettingsProvider({ children }: { children: ReactNode }) {
  const [settings, setSettings] = useState<Settings>(loadSettings)
  const [password, setPasswordState] = useState(loadPassword)

  const value = useMemo<SettingsContextValue>(
    () => ({
      settings,
      password,
      update(patch) {
        setSettings((current) => {
          const next = { ...current, ...patch }
          writeJson(localStorage, SETTINGS_KEY, next)
          return next
        })
      },
      setPassword(next) {
        writeString(sessionStorage, PASSWORD_KEY, next)
        setPasswordState(next)
      },
      reset() {
        writeJson(localStorage, SETTINGS_KEY, DEFAULT_SETTINGS)
        writeString(sessionStorage, PASSWORD_KEY, "")
        setSettings(DEFAULT_SETTINGS)
        setPasswordState("")
      },
    }),
    [settings, password]
  )

  return <SettingsContext.Provider value={value}>{children}</SettingsContext.Provider>
}
