import { AudioWaveformIcon, InboxIcon, ShieldCheckIcon } from "lucide-react"
import type { ReactNode } from "react"

import { useData, useHall, useNow } from "@/app/data"
import { SpectrumChart } from "@/components/invigil/charts"
import { EmptyState } from "@/components/invigil/empty-state"
import { Page, Panel } from "@/components/page"
import { Skeleton } from "@/components/ui/skeleton"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { isUnitOnline, messagesPerSecond } from "@/data/selectors"
import { formatAgo, formatClock, formatDbm, formatDuration } from "@/lib/format"
import { cn } from "@/lib/utils"

function Stat({ label, children, hint }: { label: string; children: ReactNode; hint?: string }) {
  return (
    <div className="flex min-w-0 flex-col gap-1 bg-card p-4">
      <span className="label-caps text-muted-foreground">{label}</span>
      <span className="truncate text-[17px] leading-6 font-medium">{children}</span>
      {hint ? <span className="line-clamp-2 text-[13px] text-muted-foreground">{hint}</span> : null}
    </div>
  )
}

const NONE = <span className="text-muted-foreground">No data</span>

export function UnitPage() {
  const { source } = useData()
  const hall = useHall()
  const now = useNow()

  const online = isUnitOnline(hall, now)
  const latest = hall.status.at(0) ?? null
  const rate = messagesPerSecond(hall, now)
  const connecting = hall.connection.phase === "connecting"
  const waitingFor =
    source.kind === "demo"
      ? "The demo unit sends one every 10 s."
      : "The unit sends one every 10 s. None has arrived: check that the broker is running and the unit or the fake publisher is on."

  return (
    <Page title="Unit" description="Sensor unit N1: a Raspberry Pi Pico 2 W with an nRF24L01 receiver, on the front wall.">
      <section
        className="col-span-12 grid grid-cols-2 gap-px overflow-hidden rounded-lg border bg-border md:grid-cols-3 xl:grid-cols-6"
        aria-label="Unit status"
      >
        {connecting ? (
          [0, 1, 2, 3, 4, 5].map((i) => (
            <div key={i} className="bg-card p-4">
              <Skeleton className="h-[72px]" />
            </div>
          ))
        ) : (
          <>
            <Stat label="Status" hint={hall.connection.detail}>
              <span className="inline-flex items-center gap-2">
                <span
                  className={cn("size-2 rounded-full", online ? "bg-clear" : "border border-line-strong")}
                  aria-hidden="true"
                />
                {online ? "Online" : "Offline"}
              </span>
            </Stat>
            <Stat label="Uptime" hint="Since the unit booted">
              {latest ? <span className="data">{formatDuration(latest.uptime_s)}</span> : NONE}
            </Stat>
            <Stat label="Wi-Fi RSSI" hint="Unit to access point">
              {latest ? <span className="data">{formatDbm(latest.wifi_rssi)}</span> : NONE}
            </Stat>
            <Stat label="Firmware" hint="Reported by the unit">
              {latest ? <span className="data">{latest.fw}</span> : NONE}
            </Stat>
            <Stat label="Messages" hint="Average over the last 10 s">
              <span className="data">{rate.toFixed(1)}</span>
              <span className="data text-[13px] font-normal text-muted-foreground"> per second</span>
            </Stat>
            <Stat label="Last seen" hint={hall.lastRxTs === null ? "Nothing received yet" : formatAgo(now - hall.lastRxTs)}>
              {hall.lastRxTs === null ? NONE : <span className="data">{formatClock(hall.lastRxTs)}</span>}
            </Stat>
          </>
        )}
      </section>

      <Panel
        className="col-span-12 xl:col-span-7"
        title="Status messages"
        description="Newest first, the last 50."
        flush
      >
        {connecting ? (
          <div className="flex flex-col gap-2 p-4">
            {[0, 1, 2, 3, 4].map((i) => (
              <Skeleton key={i} className="h-7" />
            ))}
          </div>
        ) : hall.status.length === 0 ? (
          <EmptyState icon={<InboxIcon />} title="No status messages yet">
            Each status message from the unit is listed here with its uptime, Wi-Fi signal and firmware. {waitingFor}
          </EmptyState>
        ) : (
          <div className="max-h-[26rem] overflow-y-auto">
            <Table>
              <TableHeader className="sticky top-0 bg-card">
                <TableRow className="hover:bg-transparent">
                  <TableHead className="h-9 px-4 label-caps text-muted-foreground">Unit time</TableHead>
                  <TableHead className="h-9 px-4 text-right label-caps text-muted-foreground">Uptime</TableHead>
                  <TableHead className="h-9 px-4 text-right label-caps text-muted-foreground">Wi-Fi RSSI</TableHead>
                  <TableHead className="h-9 px-4 label-caps text-muted-foreground">Firmware</TableHead>
                  <TableHead className="h-9 px-4 text-right label-caps text-muted-foreground">Latency</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {hall.status.map((s) => (
                  <TableRow key={`${s.ts}-${s.rxTs}`}>
                    <TableCell className="px-4 py-2 data text-[13px]">{formatClock(s.ts)}</TableCell>
                    <TableCell className="px-4 py-2 text-right data text-[13px]">{formatDuration(s.uptime_s)}</TableCell>
                    <TableCell className="px-4 py-2 text-right data text-[13px]">{formatDbm(s.wifi_rssi)}</TableCell>
                    <TableCell className="px-4 py-2 data text-[13px]">{s.fw}</TableCell>
                    <TableCell className="px-4 py-2 text-right data text-[13px]">{s.rxTs - s.ts} ms</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>
        )}
      </Panel>

      <Panel
        className="col-span-12 xl:col-span-5"
        title="Messages received"
        description="Every message is checked against the MQTT contract. Bad ones are dropped and counted."
        flush
      >
        <dl className="grid grid-cols-4 gap-px border-b bg-border">
          {(
            [
              ["BLE", hall.counts.ble],
              ["Spectrum", hall.counts.spectrum],
              ["Status", hall.counts.status],
              ["Rejected", hall.rejected.count],
            ] as const
          ).map(([label, count]) => (
            <div key={label} className="flex flex-col gap-1 bg-card px-4 py-3">
              <dt className="label-caps text-muted-foreground">{label}</dt>
              <dd className="data text-[17px] leading-6 font-medium">{count}</dd>
            </div>
          ))}
        </dl>
        {hall.rejected.reasons.length === 0 ? (
          <EmptyState icon={<ShieldCheckIcon />} title="No rejected messages">
            A message that breaks the contract is dropped and its reason is listed here. Every message so far has passed.
          </EmptyState>
        ) : (
          <ul className="max-h-72 divide-y overflow-y-auto">
            {hall.rejected.reasons.map((r) => (
              <li key={r.reason} className="flex items-baseline justify-between gap-4 px-4 py-2 text-[13px]">
                <span className="min-w-0">{r.reason}</span>
                <span className="shrink-0 data text-muted-foreground">
                  {r.count} · {formatClock(r.lastRxTs)}
                </span>
              </li>
            ))}
          </ul>
        )}
      </Panel>

      <Panel
        className="col-span-12"
        title="2.4 GHz channel scan"
        description={
          hall.spectrum
            ? `Carrier hits per channel in the scan window that ended ${formatClock(hall.spectrum.ts)}, ${hall.spectrum.sweeps} sweeps.`
            : "Carrier hits per channel in the latest scan window."
        }
      >
        {connecting ? (
          <Skeleton className="h-44" />
        ) : hall.spectrum ? (
          <SpectrumChart spectrum={hall.spectrum} />
        ) : (
          <EmptyState icon={<AudioWaveformIcon />} title="No spectrum message yet">
            The 126 channel hit counts from the nRF24L01 are drawn here after each scan window. None has arrived yet.
          </EmptyState>
        )}
      </Panel>
    </Page>
  )
}
