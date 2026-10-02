import { useEffect, useMemo, useState } from "react"
import type { ReactNode } from "react"

import { writeString } from "@/lib/storage"

import { THEME_KEY, ThemeContext, resolveTheme, storedTheme } from "./theme"
import type { Theme } from "./theme"

export function ThemeProvider({ children }: { children: ReactNode }) {
  const [theme, setThemeState] = useState<Theme>(storedTheme)

  useEffect(() => {
    const apply = () => {
      document.documentElement.classList.toggle("dark", resolveTheme(theme) === "dark")
    }
    apply()
    if (theme !== "system") return
    const media = window.matchMedia("(prefers-color-scheme: dark)")
    media.addEventListener("change", apply)
    return () => media.removeEventListener("change", apply)
  }, [theme])

  const value = useMemo(
    () => ({
      theme,
      setTheme(next: Theme) {
        writeString(localStorage, THEME_KEY, next)
        setThemeState(next)
      },
    }),
    [theme]
  )

  return <ThemeContext.Provider value={value}>{children}</ThemeContext.Provider>
}
