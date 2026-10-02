import { DataProvider } from "@/app/data-provider"
import { usePage } from "@/app/routes"
import type { PageId } from "@/app/routes"
import { SettingsProvider } from "@/app/settings-provider"
import { ThemeProvider } from "@/app/theme-provider"
import { AppSidebar } from "@/components/app-sidebar"
import { ConnectionNotice } from "@/components/connection-notice"
import { SiteHeader } from "@/components/site-header"
import { SidebarInset, SidebarProvider } from "@/components/ui/sidebar"
import { TooltipProvider } from "@/components/ui/tooltip"
import { LivePage } from "@/pages/live"
import { ResultsPage } from "@/pages/results"
import { SessionsPage } from "@/pages/sessions"
import { SettingsPage } from "@/pages/settings"
import { UnitPage } from "@/pages/unit"

const PAGE_COMPONENT: Record<PageId, () => React.ReactNode> = {
  live: LivePage,
  sessions: SessionsPage,
  results: ResultsPage,
  unit: UnitPage,
  settings: SettingsPage,
}

function Shell() {
  const page = usePage()
  const Current = PAGE_COMPONENT[page]

  return (
    <SidebarProvider style={{ "--sidebar-width": "13.5rem" } as React.CSSProperties}>
      <AppSidebar page={page} />
      <SidebarInset className="min-w-0">
        <SiteHeader page={page} />
        <ConnectionNotice />
        <Current />
      </SidebarInset>
    </SidebarProvider>
  )
}

export default function App() {
  return (
    <ThemeProvider>
      <SettingsProvider>
        <DataProvider>
          <TooltipProvider delayDuration={300}>
            <Shell />
          </TooltipProvider>
        </DataProvider>
      </SettingsProvider>
    </ThemeProvider>
  )
}
