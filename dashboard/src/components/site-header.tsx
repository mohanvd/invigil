import { FlaskConicalIcon, TriangleAlertIcon } from "lucide-react"

import { useData, useHall, useNow } from "@/app/data"
import { PAGES, pageHref } from "@/app/routes"
import type { PageId } from "@/app/routes"
import { useSettings } from "@/app/settings"
import { ThemeToggle } from "@/components/theme-toggle"
import {
  Breadcrumb,
  BreadcrumbItem,
  BreadcrumbList,
  BreadcrumbPage,
  BreadcrumbSeparator,
} from "@/components/ui/breadcrumb"
import { Separator } from "@/components/ui/separator"
import { SidebarTrigger } from "@/components/ui/sidebar"
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip"
import { isUnitOnline } from "@/data/selectors"
import { cn } from "@/lib/utils"

function DemoBadge() {
  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <a
          href={pageHref("settings")}
          className="inline-flex h-6 items-center gap-1.5 rounded-sm border border-line-strong bg-paper-sunken px-2 label-caps text-foreground"
        >
          <FlaskConicalIcon className="size-3" aria-hidden="true" />
          Demo data
        </a>
      </TooltipTrigger>
      <TooltipContent>Mock readings made in the browser. Switch to Live in Settings.</TooltipContent>
    </Tooltip>
  )
}

function UnitStatus() {
  const hall = useHall()
  const now = useNow()
  const online = isUnitOnline(hall, now)
  const problem = hall.connection.phase === "error" || hall.connection.phase === "reconnecting"

  return (
    <a
      href={pageHref("unit")}
      className="inline-flex h-6 items-center gap-1.5 rounded-sm px-1.5 text-[13px]"
      title={hall.connection.detail}
    >
      {problem ? (
        <TriangleAlertIcon className="size-3.5 text-muted-foreground" aria-hidden="true" />
      ) : (
        <span className={cn("size-2 rounded-full", online ? "bg-clear" : "border border-line-strong")} aria-hidden="true" />
      )}
      <span className={online ? "font-medium" : "text-muted-foreground"}>
        <span className="hidden sm:inline">Unit N1 </span>
        {problem ? "No broker" : online ? "Online" : "Offline"}
      </span>
    </a>
  )
}

export function SiteHeader({ page }: { page: PageId }) {
  const { source } = useData()
  const { settings } = useSettings()
  const title = PAGES.find((p) => p.id === page)?.title ?? ""

  return (
    <header className="sticky top-0 z-20 flex h-12 shrink-0 items-center gap-2 border-b bg-background px-4 lg:px-6">
      <SidebarTrigger className="-ml-1" />
      <Separator orientation="vertical" className="mx-1 data-[orientation=vertical]:h-4" />
      <Breadcrumb className="min-w-0">
        <BreadcrumbList className="flex-nowrap text-[13px]">
          <BreadcrumbItem className="hidden truncate md:inline-flex">{settings.hallName}</BreadcrumbItem>
          <BreadcrumbSeparator className="hidden md:block" />
          <BreadcrumbItem>
            <BreadcrumbPage className="font-medium">{title}</BreadcrumbPage>
          </BreadcrumbItem>
        </BreadcrumbList>
      </Breadcrumb>
      <div className="ml-auto flex items-center gap-2">
        {source.kind === "demo" ? <DemoBadge /> : null}
        <UnitStatus />
        <ThemeToggle />
      </div>
    </header>
  )
}
