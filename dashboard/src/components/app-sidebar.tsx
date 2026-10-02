import { ChartColumnIcon, HistoryIcon, RadioIcon, SettingsIcon } from "lucide-react"
import type { ComponentProps, ReactNode } from "react"

import { PAGES, pageHref } from "@/app/routes"
import type { PageId } from "@/app/routes"
import { UnitIcon } from "@/components/invigil/icons"
import { Mark, Wordmark } from "@/components/invigil/logo"
import {
  Sidebar,
  SidebarContent,
  SidebarFooter,
  SidebarGroup,
  SidebarGroupContent,
  SidebarHeader,
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
  SidebarRail,
  useSidebar,
} from "@/components/ui/sidebar"

const ICONS: Record<PageId, ReactNode> = {
  live: <RadioIcon />,
  sessions: <HistoryIcon />,
  results: <ChartColumnIcon />,
  unit: <UnitIcon />,
  settings: <SettingsIcon />,
}

export function AppSidebar({ page, ...props }: ComponentProps<typeof Sidebar> & { page: PageId }) {
  const { isMobile, setOpenMobile } = useSidebar()

  return (
    <Sidebar collapsible="icon" {...props}>
      <SidebarHeader>
        <a
          href={pageHref("live")}
          className="flex h-8 items-center gap-2.5 rounded-md px-1 group-data-[collapsible=icon]:justify-center group-data-[collapsible=icon]:px-0"
        >
          <Mark />
          <Wordmark className="group-data-[collapsible=icon]:hidden" />
        </a>
      </SidebarHeader>
      <SidebarContent>
        <SidebarGroup>
          <SidebarGroupContent>
            <SidebarMenu>
              {PAGES.map((p) => (
                <SidebarMenuItem key={p.id}>
                  <SidebarMenuButton asChild isActive={p.id === page} tooltip={p.title}>
                    <a
                      href={pageHref(p.id)}
                      aria-current={p.id === page ? "page" : undefined}
                      onClick={() => {
                        if (isMobile) setOpenMobile(false)
                      }}
                    >
                      {ICONS[p.id]}
                      <span>{p.title}</span>
                    </a>
                  </SidebarMenuButton>
                </SidebarMenuItem>
              ))}
            </SidebarMenu>
          </SidebarGroupContent>
        </SidebarGroup>
      </SidebarContent>
      <SidebarFooter>
        <p className="px-2 pb-1 text-[13px] text-muted-foreground group-data-[collapsible=icon]:hidden">
          Every signal leaves a trace.
        </p>
      </SidebarFooter>
      <SidebarRail />
    </Sidebar>
  )
}
