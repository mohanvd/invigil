import { createContext, useContext } from "react"

import { readString } from "@/lib/storage"

export const THEMES = ["light", "dark", "system"] as const
export type Theme = (typeof THEMES)[number]
export const THEME_LABEL: Record<Theme, string> = { light: "Light", dark: "Dark", system: "System" }

// index.html reads the same key before the first paint.
export const THEME_KEY = "invigil-theme"
export const DEFAULT_THEME: Theme = "dark"

export function storedTheme(): Theme {
  const value = readString(localStorage, THEME_KEY)
  return THEMES.find((t) => t === value) ?? DEFAULT_THEME
}

export function resolveTheme(theme: Theme): "light" | "dark" {
  if (theme !== "system") return theme
  return window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light"
}

export interface ThemeContextValue {
  theme: Theme
  setTheme(theme: Theme): void
}

export const ThemeContext = createContext<ThemeContextValue | null>(null)

export function useTheme(): ThemeContextValue {
  const value = useContext(ThemeContext)
  if (!value) throw new Error("useTheme must be used inside ThemeProvider")
  return value
}
