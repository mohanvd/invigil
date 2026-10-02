import type { ComponentProps } from "react"

import type { Band } from "@/data/types"
import { BANDS } from "@/data/types"
import { cn } from "@/lib/utils"

import { BAND_STYLE } from "./bands"

const RADIUS: Record<Band, number> = { near: 8, mid: 15, far: 22 }

interface SignalRingsProps extends Omit<ComponentProps<"svg">, "children"> {
  /** The band to light. null draws the unit with all three arcs quiet. */
  band: Band | null
}

/**
 * The unit on the front wall with three half arcs spreading into the room.
 * Only the current band's arc is lit, in its color.
 */
export function SignalRings({ band, className, ...props }: SignalRingsProps) {
  return (
    <svg
      xmlns="http://www.w3.org/2000/svg"
      viewBox="0 0 52 30"
      width="39"
      height="22.5"
      fill="none"
      role="img"
      aria-label={band ? `${band} band` : "no band"}
      className={cn("shrink-0 text-foreground", className)}
      {...props}
    >
      {BANDS.map((b) => {
        const r = RADIUS[b]
        return (
          <path
            key={b}
            d={`M${26 - r} 4A${r} ${r} 0 0 0 ${26 + r} 4`}
            stroke={b === band ? BAND_STYLE[b].stroke : "var(--border)"}
            strokeWidth="3"
          />
        )
      })}
      <path d="M1 2.5h50" stroke="currentColor" strokeWidth="3" />
      <circle cx="26" cy="3.5" r="3.5" fill="currentColor" />
    </svg>
  )
}
