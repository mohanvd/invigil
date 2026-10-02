import type { ComponentProps } from "react"

import type { Band } from "@/data/types"
import { cn } from "@/lib/utils"

import { BAND_STYLE } from "./bands"

/** A distance band: its color and always its word, so it reads in grayscale too. */
export function BandChip({ band, className, ...props }: ComponentProps<"span"> & { band: Band }) {
  const style = BAND_STYLE[band]
  return (
    <span
      className={cn(
        "inline-flex h-5 shrink-0 items-center gap-1.5 rounded-sm px-1.5 label-caps text-foreground",
        style.soft,
        className
      )}
      {...props}
    >
      <span className={cn("size-2 rounded-full", style.mark)} aria-hidden="true" />
      {band}
    </span>
  )
}
