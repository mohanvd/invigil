import { MonitorIcon, MoonIcon, SunIcon } from "lucide-react"
import type { ReactNode } from "react"

import { THEMES, THEME_LABEL, useTheme } from "@/app/theme"
import type { Theme } from "@/app/theme"
import { Button } from "@/components/ui/button"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuRadioGroup,
  DropdownMenuRadioItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"

const THEME_ICON: Record<Theme, ReactNode> = { light: <SunIcon />, dark: <MoonIcon />, system: <MonitorIcon /> }

export function ThemeToggle() {
  const { theme, setTheme } = useTheme()

  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button variant="ghost" size="icon-sm" aria-label={`Theme: ${THEME_LABEL[theme]}. Change theme.`}>
          {THEME_ICON[theme]}
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" className="w-36">
        <DropdownMenuRadioGroup value={theme} onValueChange={(value) => setTheme(THEMES.find((t) => t === value) ?? theme)}>
          {THEMES.map((t) => (
            <DropdownMenuRadioItem key={t} value={t}>
              {THEME_ICON[t]}
              {THEME_LABEL[t]}
            </DropdownMenuRadioItem>
          ))}
        </DropdownMenuRadioGroup>
      </DropdownMenuContent>
    </DropdownMenu>
  )
}
