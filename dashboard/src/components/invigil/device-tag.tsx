import type { ComponentProps } from "react"

import type { DeviceType } from "@/data/types"
import { cn } from "@/lib/utils"

import { DEVICE_LABEL } from "./bands"
import { DeviceIcon } from "./icons"

interface DeviceTagProps extends ComponentProps<"span"> {
  type: DeviceType
  /** A name to show instead of the type, for example a whitelist label. */
  label?: string
}

/** A device type: icon and word. Types are never told apart by color; only allowed is tinted. */
export function DeviceTag({ type, label, className, ...props }: DeviceTagProps) {
  return (
    <span className={cn("inline-flex min-w-0 items-center gap-1.5 font-medium", className)} {...props}>
      <DeviceIcon type={type} className={cn("shrink-0", type === "allowed" && "text-clear")} />
      <span className="truncate">{label ?? DEVICE_LABEL[type]}</span>
    </span>
  )
}

/** A hashed address. Addresses only ever appear as 12-character hashes in mono. */
export function Hash({ addr, className, ...props }: ComponentProps<"span"> & { addr: string | null }) {
  if (addr === null) {
    return (
      <span className={cn("text-muted-foreground", className)} {...props}>
        no address
      </span>
    )
  }
  return (
    <span className={cn("data text-[13px] text-muted-foreground", className)} {...props}>
      {addr}
    </span>
  )
}
