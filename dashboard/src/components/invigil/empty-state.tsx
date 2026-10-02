import type { ComponentProps, ReactNode } from "react"

import { cn } from "@/lib/utils"

interface EmptyStateProps extends Omit<ComponentProps<"div">, "title"> {
  /** What will appear here. */
  title: ReactNode
  /** Why it is empty right now. */
  children: ReactNode
  icon?: ReactNode
}

export function EmptyState({ title, children, icon, className, ...props }: EmptyStateProps) {
  return (
    <div
      className={cn("flex flex-col items-center justify-center gap-1 px-6 py-10 text-center", className)}
      {...props}
    >
      {icon ? <div className="mb-2 text-muted-foreground [&_svg]:size-5">{icon}</div> : null}
      <p className="font-medium">{title}</p>
      <p className="max-w-[46ch] text-[13px] text-muted-foreground">{children}</p>
    </div>
  )
}
