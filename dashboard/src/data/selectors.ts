import type { Alert, Band, Detection, DeviceType, HallState, HeardDevice } from "./types"

/** The unit sends a status message every 10 s, so 15 s of silence means offline. */
export const UNIT_STALE_MS = 15_000
/** A device stays on the hall map this long after its last detection. */
export const DEVICE_STALE_MS = 15_000
export const HEARD_WINDOW_MS = 60_000

export interface AllowedDevice {
  addr: string
  label: string
}

export function percentile(values: number[], p: number): number | null {
  if (values.length === 0) return null
  const sorted = [...values].sort((a, b) => a - b)
  const rank = (p / 100) * (sorted.length - 1)
  const lo = Math.floor(rank)
  const hi = Math.ceil(rank)
  return sorted[lo] + (sorted[hi] - sorted[lo]) * (rank - lo)
}

export function isUnitOnline(state: HallState, now: number): boolean {
  return state.lastRxTs !== null && now - state.lastRxTs <= UNIT_STALE_MS
}

export function messagesPerSecond(state: HallState, now: number, windowMs = 10_000): number {
  const cutoff = now - windowMs
  const recent = state.rxTimes.filter((t) => t > cutoff && t <= now)
  return recent.length / (windowMs / 1000)
}

export function devicesHeard(state: HallState, now: number, windowMs = HEARD_WINDOW_MS): HeardDevice[] {
  const cutoff = now - windowMs
  return Object.values(state.heard)
    .filter((d) => d.lastTs > cutoff)
    .sort((a, b) => b.lastTs - a.lastTs)
}

export function allowedLabel(addr: string | null, allowed: AllowedDevice[]): string | null {
  if (addr === null) return null
  return allowed.find((a) => a.addr === addr)?.label ?? null
}

export interface AlertFilter {
  type: DeviceType | "all"
  band: Band | "all"
}

/** Alerts for the list: whitelisted devices removed, filters applied, newest first. */
export function visibleAlerts(alerts: Alert[], allowed: AllowedDevice[], filter: AlertFilter): Alert[] {
  return alerts
    .filter((a) => allowedLabel(a.addr, allowed) === null)
    .filter((a) => filter.type === "all" || a.type === filter.type)
    .filter((a) => filter.band === "all" || a.band === filter.band)
    .sort((a, b) => b.firstTs - a.firstTs)
}

export function activeAlertCount(alerts: Alert[], allowed: AllowedDevice[]): number {
  return alerts.filter((a) => a.state === "new" && allowedLabel(a.addr, allowed) === null).length
}

export function alertLatencyP50(alerts: Alert[]): number | null {
  return percentile(
    alerts.map((a) => a.latencyMs),
    50
  )
}

export function messageLatencyP50(state: HallState): number | null {
  return percentile(
    state.latencies.map((l) => l.ms),
    50
  )
}

/** Alerts the invigilator marked as false, per hour since the dashboard started listening. */
export function falseAlarmsPerHour(state: HallState, now: number): number | null {
  const hours = (now - state.startedAt) / 3_600_000
  if (hours <= 0) return null
  const marked = state.alerts.filter((a) => a.state === "false_alarm").length
  return marked / hours
}

export interface MapDevice {
  key: string
  addr: string | null
  type: DeviceType
  band: Band
  label: string | null
}

/** Devices to draw on the hall map: detected recently, whitelisted ones shown as allowed. */
export function mapDevices(state: HallState, allowed: AllowedDevice[], now: number): MapDevice[] {
  const cutoff = now - DEVICE_STALE_MS
  return Object.entries(state.detections)
    .filter(([, d]: [string, Detection]) => d.ts > cutoff)
    .map(([key, d]) => {
      const label = allowedLabel(d.addr, allowed)
      return {
        key,
        addr: d.addr,
        type: label === null ? d.type : "allowed",
        band: d.band,
        label,
      }
    })
    .sort((a, b) => a.key.localeCompare(b.key))
}
