import { CheckIcon, EllipsisIcon } from "lucide-react"

import { Button } from "@/components/ui/button"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import type { Alert, AlertState } from "@/data/types"
import { formatAgo, formatClock, formatDbm, formatPercent } from "@/lib/format"
import { cn } from "@/lib/utils"

import { BandChip } from "./band-chip"
import { BAND_STYLE, DEVICE_LABEL } from "./bands"
import { DeviceTag, Hash } from "./device-tag"
import { SignalRings } from "./signal-rings"

interface DetectionAlertProps {
  alert: Alert
  now: number
  selected: boolean
  onSelect(alert: Alert): void
  onStateChange(id: string, state: AlertState): void
}

const STATE_WORD: Record<AlertState, string> = {
  new: "New",
  acknowledged: "Acknowledged",
  false_alarm: "Marked as false alarm",
}

/** One alert row. A new alert sits on its band's soft tint until someone handles it. */
export function DetectionAlert({ alert, now, selected, onSelect, onStateChange }: DetectionAlertProps) {
  const isNew = alert.state === "new"
  const device = DEVICE_LABEL[alert.type]

  return (
    <li
      className={cn(
        "flex items-center gap-3 rounded-md border px-3 py-2",
        isNew ? BAND_STYLE[alert.band].soft : "bg-card",
        selected && "border-line-strong"
      )}
    >
      <button
        type="button"
        onClick={() => onSelect(alert)}
        aria-pressed={selected}
        aria-label={`${device}, ${alert.band} band. Show signal strength.`}
        className="grid min-w-0 flex-1 cursor-pointer grid-cols-[auto_minmax(0,1fr)] items-center gap-x-3 gap-y-1 rounded-sm text-left sm:grid-cols-[auto_minmax(0,1fr)_auto_auto]"
      >
        <SignalRings band={alert.band} className={cn(!isNew && "opacity-70")} />
        <span className="flex min-w-0 flex-col">
          <span className="flex min-w-0 items-baseline gap-2">
            <DeviceTag type={alert.type} />
            <span className="data text-[13px] text-muted-foreground" title="Device type confidence">
              {formatPercent(alert.typeConf)}
            </span>
          </span>
          <Hash addr={alert.addr} className={alert.addr === null ? "text-[13px]" : undefined} />
        </span>
        <BandChip band={alert.band} className="col-start-2 justify-self-start sm:col-start-auto" />
        <span className="col-start-2 flex flex-col text-[13px] whitespace-nowrap sm:col-start-auto sm:text-right">
          {alert.rssi === null ? (
            <span className="text-muted-foreground">Spectrum only</span>
          ) : (
            <span className="data">{formatDbm(alert.rssi)}</span>
          )}
          <span className="data text-muted-foreground" title={`Last detected ${formatAgo(now - alert.lastTs)}`}>
            {formatClock(alert.firstTs)}
          </span>
        </span>
      </button>

      <div className="flex shrink-0 items-center gap-1">
        {isNew ? (
          <Button size="sm" variant="outline" className="bg-card" onClick={() => onStateChange(alert.id, "acknowledged")}>
            <CheckIcon data-icon="inline-start" />
            Acknowledge
          </Button>
        ) : (
          <span className="hidden text-[13px] text-muted-foreground md:inline">{STATE_WORD[alert.state]}</span>
        )}
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <Button size="icon-sm" variant="ghost" aria-label={`More actions for this ${device.toLowerCase()} alert`}>
              <EllipsisIcon />
            </Button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="end" className="w-52">
            <DropdownMenuItem disabled={alert.state === "acknowledged"} onSelect={() => onStateChange(alert.id, "acknowledged")}>
              Acknowledge
            </DropdownMenuItem>
            <DropdownMenuItem disabled={alert.state === "false_alarm"} onSelect={() => onStateChange(alert.id, "false_alarm")}>
              Mark as false alarm
            </DropdownMenuItem>
            <DropdownMenuItem disabled={isNew} onSelect={() => onStateChange(alert.id, "new")}>
              Reopen
            </DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>
      </div>
    </li>
  )
}
