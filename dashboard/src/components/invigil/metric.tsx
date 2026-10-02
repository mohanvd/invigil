import { CheckIcon, CircleDashedIcon, XIcon } from "lucide-react"
import type { ComponentProps, ReactNode } from "react"

import type { RequirementStatus } from "@/data/types"
import { cn } from "@/lib/utils"

const STATUS: Record<RequirementStatus, { word: string; icon: ReactNode; className: string }> = {
  // A pass is clear. A fail is words and an icon on neutrals: red means near, not failure.
  pass: { word: "Pass", icon: <CheckIcon />, className: "bg-clear-soft text-foreground [&_svg]:text-clear" },
  fail: { word: "Fail", icon: <XIcon />, className: "border border-line-strong bg-paper-sunken text-foreground" },
  pending: {
    word: "Pending",
    icon: <CircleDashedIcon />,
    className: "border border-dashed border-line-strong text-muted-foreground",
  },
}

export function StatusChip({ status, className }: { status: RequirementStatus; className?: string }) {
  const s = STATUS[status]
  return (
    <span
      className={cn(
        "inline-flex h-5 shrink-0 items-center gap-1 rounded-sm px-1.5 label-caps [&_svg]:size-3",
        s.className,
        className
      )}
    >
      {s.icon}
      {s.word}
    </span>
  )
}

interface MetricProps extends Omit<ComponentProps<"div">, "children"> {
  label: string
  /** The measured value, already formatted. null means there is no value yet. */
  value: string | null
  unit?: string
  /** The target the value is judged against. */
  target?: string
  status?: RequirementStatus
  /** One line under the value: where the number comes from, or why there is none. */
  hint?: ReactNode
  size?: "default" | "lg"
}

/** One result number with its label, its target, and pass, fail or pending. */
export function Metric({ label, value, unit, target, status, hint, size = "default", className, ...props }: MetricProps) {
  return (
    <div className={cn("flex min-w-0 flex-col gap-2 rounded-lg border bg-card p-4", className)} {...props}>
      <div className="flex items-start justify-between gap-2">
        <span className="label-caps text-muted-foreground">{label}</span>
        {status ? <StatusChip status={status} /> : null}
      </div>
      <div className="flex items-baseline gap-1.5">
        {value === null ? (
          <span className={cn("data text-muted-foreground", size === "lg" ? "text-[40px] leading-[44px]" : "text-[28px] leading-8")}>
            No data
          </span>
        ) : (
          <>
            <span
              className={cn(
                "data font-medium tracking-[-0.02em]",
                size === "lg" ? "text-[40px] leading-[44px]" : "text-[28px] leading-8"
              )}
            >
              {value}
              {unit === "%" ? "%" : null}
            </span>
            {unit && unit !== "%" ? <span className="data text-[13px] text-muted-foreground">{unit}</span> : null}
          </>
        )}
      </div>
      {target ? (
        <div className="text-[13px]">
          <span className="text-muted-foreground">Target </span>
          <span className="data">{target}</span>
        </div>
      ) : null}
      {hint ? <p className="text-[13px] text-muted-foreground">{hint}</p> : null}
    </div>
  )
}
