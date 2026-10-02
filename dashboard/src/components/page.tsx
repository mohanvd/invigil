import type { ComponentProps, ReactNode } from "react"

import { cn } from "@/lib/utils"

interface PageProps {
  title: string
  description: ReactNode
  actions?: ReactNode
  children: ReactNode
}

/** A page: one Archivo title, one line of context, then the content on a 12-column grid. */
export function Page({ title, description, actions, children }: PageProps) {
  return (
    <main className="flex flex-1 flex-col gap-6 p-4 lg:p-6">
      <div className="flex flex-wrap items-end justify-between gap-x-6 gap-y-3">
        <div className="min-w-0">
          <h1 className="font-display text-[22px] leading-7 font-bold tracking-[-0.01em]">{title}</h1>
          <p className="mt-0.5 max-w-[70ch] text-[13px] text-muted-foreground">{description}</p>
        </div>
        {actions ? <div className="flex items-center gap-2">{actions}</div> : null}
      </div>
      <div className="grid grid-cols-12 gap-4">{children}</div>
    </main>
  )
}

interface PanelProps extends Omit<ComponentProps<"section">, "title"> {
  title: string
  description?: ReactNode
  actions?: ReactNode
  /** Remove the body padding, for tables and lists that run edge to edge. */
  flush?: boolean
}

/** A bordered card with a title row. Borders, not shadows. */
export function Panel({ title, description, actions, flush = false, className, children, ...props }: PanelProps) {
  return (
    <section className={cn("flex min-w-0 flex-col rounded-lg border bg-card", className)} {...props}>
      <header className="flex min-h-12 flex-wrap items-center justify-between gap-x-4 gap-y-2 border-b px-4 py-2">
        <div className="min-w-0">
          <h2 className="font-semibold">{title}</h2>
          {description ? <p className="text-[13px] text-muted-foreground">{description}</p> : null}
        </div>
        {actions ? <div className="flex flex-wrap items-center gap-2">{actions}</div> : null}
      </header>
      <div className={cn("flex min-h-0 flex-1 flex-col", !flush && "p-4")}>{children}</div>
    </section>
  )
}
