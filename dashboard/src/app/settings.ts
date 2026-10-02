import { createContext, useContext } from "react"

import type { AllowedDevice } from "@/data/selectors"
import type { SourceKind } from "@/data/types"
import { readJson, readString } from "@/lib/storage"

export interface Settings {
  source: SourceKind
  /** WebSockets URL of the Mosquitto listener. */
  brokerUrl: string
  username: string
  hallName: string
  allowed: AllowedDevice[]
}

export const SETTINGS_KEY = "invigil-settings"
// The broker password is kept for the browser tab only and never written to
// localStorage.
export const PASSWORD_KEY = "invigil-mqtt-password"

export const DEFAULT_SETTINGS: Settings = {
  source: "demo",
  brokerUrl: "ws://localhost:9001",
  username: "",
  hallName: "Mini hall",
  allowed: [],
}

export const HASH_RE = /^[0-9a-f]{12}$/

export function isBrokerUrl(value: string): boolean {
  try {
    const url = new URL(value)
    return url.protocol === "ws:" || url.protocol === "wss:"
  } catch {
    return false
  }
}

function isAllowedDevice(value: unknown): value is AllowedDevice {
  if (typeof value !== "object" || value === null) return false
  const v = value as Record<string, unknown>
  return typeof v.addr === "string" && HASH_RE.test(v.addr) && typeof v.label === "string"
}

/** Stored settings, with anything missing or malformed replaced by the default. */
export function loadSettings(): Settings {
  const raw = readJson(localStorage, SETTINGS_KEY)
  if (typeof raw !== "object" || raw === null) return DEFAULT_SETTINGS
  const r = raw as Record<string, unknown>
  return {
    source: r.source === "live" ? "live" : "demo",
    brokerUrl: typeof r.brokerUrl === "string" && isBrokerUrl(r.brokerUrl) ? r.brokerUrl : DEFAULT_SETTINGS.brokerUrl,
    username: typeof r.username === "string" ? r.username : "",
    hallName: typeof r.hallName === "string" && r.hallName.trim() !== "" ? r.hallName : DEFAULT_SETTINGS.hallName,
    allowed: Array.isArray(r.allowed) ? r.allowed.filter(isAllowedDevice) : [],
  }
}

export function loadPassword(): string {
  return readString(sessionStorage, PASSWORD_KEY) ?? ""
}

export interface SettingsContextValue {
  settings: Settings
  password: string
  update(patch: Partial<Settings>): void
  setPassword(password: string): void
  reset(): void
}

export const SettingsContext = createContext<SettingsContextValue | null>(null)

export function useSettings(): SettingsContextValue {
  const value = useContext(SettingsContext)
  if (!value) throw new Error("useSettings must be used inside SettingsProvider")
  return value
}
