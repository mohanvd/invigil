// The Invigil mark from docs/brand/logo: the hall from above, the unit on the
// front wall, and the near, mid and far arcs. Drawn with theme colors, which
// are the same values as invigil-mark.svg (light) and invigil-mark-dark.svg.

import { useId } from "react"
import type { ComponentProps } from "react"

import { cn } from "@/lib/utils"

export function Mark({ className, ...props }: Omit<ComponentProps<"svg">, "children">) {
  const clipId = useId()
  return (
    <svg
      xmlns="http://www.w3.org/2000/svg"
      viewBox="0 0 64 64"
      width="24"
      height="24"
      role="img"
      aria-label="Invigil"
      className={cn("shrink-0 text-(--logo-ink)", className)}
      {...props}
    >
      <defs>
        <clipPath id={clipId}>
          <rect x="5" y="5" width="54" height="54" />
        </clipPath>
      </defs>
      <g clipPath={`url(#${clipId})`} fill="none" strokeWidth="5.5">
        <circle cx="32" cy="2.5" r="16" stroke="var(--near)" />
        <circle cx="32" cy="2.5" r="29" stroke="var(--mid)" />
        <circle cx="32" cy="2.5" r="42" stroke="var(--far)" />
      </g>
      <rect x="2.5" y="2.5" width="59" height="59" fill="none" stroke="currentColor" strokeWidth="5" />
      <circle cx="32" cy="2.5" r="7.5" fill="currentColor" />
    </svg>
  )
}

/** The wordmark is "invigil" in Archivo Bold, lowercase. */
export function Wordmark({ className, ...props }: ComponentProps<"span">) {
  return (
    <span
      className={cn("font-display text-[19px] leading-none font-bold tracking-[-0.01em] text-(--logo-ink)", className)}
      {...props}
    >
      invigil
    </span>
  )
}
