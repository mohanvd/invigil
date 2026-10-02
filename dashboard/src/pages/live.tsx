import { BellOffIcon, MapPinOffIcon, WavesIcon } from "lucide-react"
import { useMemo, useState } from "react"

import { useData, useHall, useNow } from "@/app/data"
import { useSettings } from "@/app/settings"
import { BAND_RANGE, DEVICE_LABEL } from "@/components/invigil/bands"
import { RssiTimeChart } from "@/components/invigil/charts"
import { DetectionAlert } from "@/components/invigil/detection-alert"
import { EmptyState } from "@/components/invigil/empty-state"
import { HallMap } from "@/components/invigil/hall-map"
import { Metric } from "@/components/invigil/metric"
import { Page, Panel } from "@/components/page"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Skeleton } from "@/components/ui/skeleton"
import {
  activeAlertCount,
  alertLatencyP50,
  allowedLabel,
  devicesHeard,
  falseAlarmsPerHour,
  mapDevices,
  messageLatencyP50,
  visibleAlerts,
} from "@/data/selectors"
import type { AlertFilter } from "@/data/selectors"
import { BANDS, DEVICE_TYPES } from "@/data/types"
import type { Band, DeviceType } from "@/data/types"

const RSSI_WINDOW_MS = 180_000
const ALERT_TYPES = DEVICE_TYPES.filter((t) => t !== "allowed")

function LoadingLive() {
  return (
    <>
      {[0, 1, 2, 3].map((i) => (
        <Skeleton key={i} className="col-span-6 h-[116px] rounded-lg xl:col-span-3" />
      ))}
      <Skeleton className="col-span-12 h-96 rounded-lg xl:col-span-5" />
      <Skeleton className="col-span-12 h-96 rounded-lg xl:col-span-7" />
      <Skeleton className="col-span-12 h-72 rounded-lg" />
    </>
  )
}

export function LivePage() {
  const { store, source } = useData()
  const { settings } = useSettings()
  const hall = useHall()
  const now = useNow()
  const [filter, setFilter] = useState<AlertFilter>({ type: "all", band: "all" })
  const [picked, setPicked] = useState<string | null>(null)

  const isDemo = source.kind === "demo"
  const alerts = useMemo(() => visibleAlerts(hall.alerts, settings.allowed, filter), [hall.alerts, settings.allowed, filter])
  const allAlerts = useMemo(
    () => visibleAlerts(hall.alerts, settings.allowed, { type: "all", band: "all" }),
    [hall.alerts, settings.allowed]
  )
  const devices = mapDevices(hall, settings.allowed, now)
  const heard = devicesHeard(hall, now)
  const everHeard = useMemo(() => Object.values(hall.heard).sort((a, b) => b.lastTs - a.lastTs), [hall.heard])

  // The device whose signal is charted: the one picked, or the most recent one heard.
  const selectedAddr = picked !== null && hall.heard[picked] ? picked : (everHeard[0]?.addr ?? null)
  const selected = selectedAddr ? hall.heard[selectedAddr] : null
  const readings = selected ? selected.readings.filter((r) => r.ts > now - RSSI_WINDOW_MS) : []

  const active = activeAlertCount(hall.alerts, settings.allowed)
  const alertLatency = alertLatencyP50(allAlerts)
  const latency = alertLatency ?? messageLatencyP50(hall)
  const falseRate = falseAlarmsPerHour(hall, now)

  const connecting = hall.connection.phase === "connecting"

  function nameOf(addr: string): string {
    const label = allowedLabel(addr, settings.allowed)
    if (label) return label
    const detection = hall.detections[addr]
    return detection ? DEVICE_LABEL[detection.type] : "Not classified"
  }

  return (
    <Page
      title="Live"
      description={`${settings.hallName}: one unit on the front wall, listening for phones, earpieces and smartwatches.`}
    >
      {connecting ? (
        <LoadingLive />
      ) : (
        <>
          <Metric
            className="col-span-6 xl:col-span-3"
            label="Active alerts"
            value={String(active)}
            hint={
              allAlerts.length === 0
                ? isDemo
                  ? "No device has been flagged yet."
                  : "Detections are not on MQTT yet."
                : `${allAlerts.length} raised since this page opened.`
            }
          />
          <Metric
            className="col-span-6 xl:col-span-3"
            label="Devices heard"
            value={String(heard.length)}
            hint="Hashed addresses heard on Bluetooth in the last minute."
          />
          <Metric
            className="col-span-6 xl:col-span-3"
            label="Alert latency p50"
            value={latency === null ? null : (latency / 1000).toFixed(2)}
            unit="s"
            hint={
              latency === null
                ? "Appears with the first message from the unit."
                : alertLatency === null
                  ? "No alerts yet: this is message latency, unit to dashboard."
                  : "Unit to dashboard. The target is within 2 s."
            }
          />
          <Metric
            className="col-span-6 xl:col-span-3"
            label="False alarms"
            value={falseRate === null ? null : falseRate.toFixed(1)}
            unit="per hour"
            hint="Alerts you mark as false, since this page opened."
          />

          <Panel
            className="col-span-12 xl:col-span-5"
            title="Hall map"
            description="Seen from above. The bands spread from the unit."
          >
            <div className="relative">
              <HallMap
                devices={devices}
                selectedKey={selectedAddr}
                onSelect={(device) => {
                  if (device.addr) setPicked(device.addr)
                }}
              />
              {devices.length === 0 ? (
                <div className="absolute inset-x-6 bottom-6 rounded-md border bg-card">
                  <EmptyState className="py-4" icon={<MapPinOffIcon />} title="No devices on the map">
                    {isDemo
                      ? "A device appears in its band once the model has flagged it. None was detected in the last 15 s."
                      : "Devices appear in their band once detections are published. The detection topic is only a proposal so far, so the map fills in Demo only."}
                  </EmptyState>
                </div>
              ) : null}
            </div>
            <p className="mt-3 text-[13px] text-muted-foreground">
              Devices are placed by distance band only. Where a device sits along its arc is not measured.
            </p>
          </Panel>

          <Panel
            className="col-span-12 xl:col-span-7"
            title="Alerts"
            description="Newest first."
            flush
            actions={
              <>
                <Select
                  value={filter.type}
                  onValueChange={(value) => setFilter((f) => ({ ...f, type: value as DeviceType | "all" }))}
                >
                  <SelectTrigger size="sm" className="w-36" aria-label="Filter by device type">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="all">All device types</SelectItem>
                    {ALERT_TYPES.map((t) => (
                      <SelectItem key={t} value={t}>
                        {DEVICE_LABEL[t]}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
                <Select value={filter.band} onValueChange={(value) => setFilter((f) => ({ ...f, band: value as Band | "all" }))}>
                  <SelectTrigger size="sm" className="w-36" aria-label="Filter by distance band">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="all">All bands</SelectItem>
                    {BANDS.map((b) => (
                      <SelectItem key={b} value={b}>
                        <span className="capitalize">{b}</span>
                        <span className="text-muted-foreground">{BAND_RANGE[b]}</span>
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </>
            }
          >
            {alerts.length === 0 ? (
              <EmptyState className="flex-1" icon={<BellOffIcon />} title="No alerts to show">
                {allAlerts.length > 0
                  ? "No alert matches these filters. Change the device type or the band to see the others."
                  : isDemo
                    ? "An alert appears here when the model flags a phone, an earpiece or a smartwatch. Nothing has been flagged yet."
                    : "An alert appears here when the model flags a device. Detections are not published on MQTT yet, so this list fills in Demo only."}
              </EmptyState>
            ) : (
              <ul className="flex max-h-[30rem] flex-col gap-2 overflow-y-auto p-3">
                {alerts.map((alert) => (
                  <DetectionAlert
                    key={alert.id}
                    alert={alert}
                    now={now}
                    selected={alert.addr !== null && alert.addr === selectedAddr}
                    onSelect={(a) => {
                      if (a.addr) setPicked(a.addr)
                    }}
                    onStateChange={store.setAlertState}
                  />
                ))}
              </ul>
            )}
          </Panel>

          <Panel
            className="col-span-12"
            title="RSSI over time"
            description="Bluetooth signal strength of one device in dBm, over the last 3 minutes."
            actions={
              everHeard.length > 0 && selectedAddr ? (
                <Select value={selectedAddr} onValueChange={setPicked}>
                  <SelectTrigger size="sm" className="w-64" aria-label="Device to chart">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {everHeard.map((d) => (
                      <SelectItem key={d.addr} value={d.addr}>
                        <span className="data text-[13px]">{d.addr}</span>
                        <span className="text-muted-foreground">{nameOf(d.addr)}</span>
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              ) : null
            }
          >
            {selected === null ? (
              <EmptyState icon={<WavesIcon />} title="No device to chart">
                The signal strength of a device is drawn here as soon as the unit hears a Bluetooth advertisement. Nothing
                has been heard yet. An earpiece that only streams audio never appears here, because it sends no
                advertisements.
              </EmptyState>
            ) : readings.length === 0 ? (
              <EmptyState icon={<WavesIcon />} title="No readings in the last 3 minutes">
                This device was heard earlier but has been silent since. New readings are drawn as they arrive.
              </EmptyState>
            ) : (
              <RssiTimeChart readings={readings} from={now - RSSI_WINDOW_MS} to={now} />
            )}
          </Panel>
        </>
      )}
    </Page>
  )
}
