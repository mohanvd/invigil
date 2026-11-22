import type { NearDevice } from "@/data/selectors"
import { formatDbm, formatPercent } from "@/lib/format"
import { cn } from "@/lib/utils"

import { DEVICE_LABEL } from "./bands"
import { Hash } from "./device-tag"
import { DeviceIcon } from "./icons"
import { SignalRings } from "./signal-rings"

interface NearBannerProps {
  devices: NearDevice[]
  className?: string
}

/**
 * Search mode: the invigilator carries the unit along the rows. When a banned
 * device is within 1 m, this names it in letters big enough to read at arm's
 * length. With nothing near, it stays as a quiet line so the layout does not jump.
 */
export function NearBanner({ devices, className }: NearBannerProps) {
  const top = devices[0]
  if (!top) {
    return (
      <section
        role="status"
        aria-live="polite"
        className={cn("flex items-center gap-3 rounded-lg border bg-card px-4 py-3", className)}
      >
        <SignalRings band={null} />
        <p className="text-[15px] text-muted-foreground">
          <span className="label-caps text-foreground">Search mode</span> Nothing banned within 1 m of the unit.
        </p>
      </section>
    )
  }

  const type = DEVICE_LABEL[top.type]
  const others = devices.length - 1
  return (
    <section
      role="alert"
      aria-live="assertive"
      aria-label={`Near: ${type}`}
      className={cn("flex flex-wrap items-center gap-x-6 gap-y-3 rounded-lg border-2 border-near bg-near-soft px-5 py-4", className)}
    >
      <DeviceIcon type={top.type} width="56" height="56" className="shrink-0 text-foreground" />
      <div className="flex min-w-0 flex-1 flex-col gap-1">
        <p className="font-display text-5xl leading-none font-bold tracking-tight text-foreground uppercase sm:text-6xl">
          Near: {type}
        </p>
        <p className="flex flex-wrap items-baseline gap-x-3 text-[15px] text-foreground">
          <span>Within 1 m of the unit. Check the closest seat.</span>
          {top.rssi === null ? null : <span className="data">{formatDbm(top.rssi)}</span>}
          <span className="data text-muted-foreground" title="Model confidence that the device is near">
            {formatPercent(top.bandConf)} sure
          </span>
          <Hash addr={top.addr} />
        </p>
      </div>
      {others > 0 ? (
        <p className="label-caps text-foreground">
          +{others} more near: {devices.slice(1).map((d) => DEVICE_LABEL[d.type]).join(", ")}
        </p>
      ) : null}
    </section>
  )
}
