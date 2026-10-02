import { decode } from "./contract"
import type {
  Alert,
  AlertState,
  ConnectionState,
  DataSink,
  Detection,
  HallState,
  HeardDevice,
  RejectReason,
} from "./types"
import { BANDS, DEVICE_TYPES } from "./types"

export const MAX_READINGS_PER_DEVICE = 600
export const MAX_STATUS_ENTRIES = 50
export const MAX_REJECT_REASONS = 20
export const RATE_WINDOW_MS = 10_000
export const LATENCY_WINDOW_MS = 60_000

const ADDR_RE = /^[0-9a-f]{12}$/

function emptyState(now: number): HallState {
  return {
    connection: { phase: "idle", detail: "Not connected" },
    heard: {},
    spectrum: null,
    status: [],
    alerts: [],
    detections: {},
    counts: { ble: 0, spectrum: 0, status: 0, detection: 0 },
    rejected: { count: 0, reasons: [] },
    rxTimes: [],
    latencies: [],
    lastRxTs: null,
    startedAt: now,
  }
}

export function deviceKey(d: { addr: string | null; node: string; type: string }): string {
  return d.addr ?? `${d.node}:spectrum:${d.type}`
}

function isUnitInterval(value: unknown): value is number {
  return typeof value === "number" && value >= 0 && value <= 1
}

/** Check a detection against the proposed payload in docs/contract.md. */
export function detectionProblem(d: Detection): string | null {
  if (!Number.isInteger(d.ts)) return "ts must be an integer"
  if (d.addr !== null && !ADDR_RE.test(d.addr)) return "addr must be null or a hashed address"
  if (!DEVICE_TYPES.includes(d.type)) return "unknown device type"
  if (!BANDS.includes(d.band)) return "unknown distance band"
  if (!isUnitInterval(d.type_conf) || !isUnitInterval(d.band_conf)) {
    return "confidence must be between 0 and 1"
  }
  if (d.rssi !== null && (!Number.isInteger(d.rssi) || d.rssi < -127 || d.rssi > 0)) {
    return "rssi must be null or an integer from -127 to 0"
  }
  return null
}

export interface HallStore extends DataSink {
  subscribe(listener: () => void): () => void
  getSnapshot(): HallState
  setAlertState(id: string, state: AlertState): void
  reset(): void
  /** Publish pending changes now instead of waiting for the next tick. */
  flush(): void
}

export interface StoreOptions {
  now?: () => number
  /** Minimum time between snapshots, so a busy hall does not re-render per packet. */
  notifyEveryMs?: number
}

export function createHallStore(options: StoreOptions = {}): HallStore {
  const now = options.now ?? Date.now
  const notifyEveryMs = options.notifyEveryMs ?? 250

  let state = emptyState(now())
  let snapshot = state
  let dirty = false
  let timer: ReturnType<typeof setTimeout> | null = null
  const listeners = new Set<() => void>()

  function publish() {
    timer = null
    if (!dirty) return
    dirty = false
    snapshot = { ...state }
    for (const listener of listeners) listener()
  }

  function touch() {
    dirty = true
    if (notifyEveryMs <= 0) {
      publish()
    } else if (timer === null) {
      timer = setTimeout(publish, notifyEveryMs)
    }
  }

  function reject(reason: string, rxTs: number) {
    const reasons = state.rejected.reasons.filter((r) => r.reason !== reason)
    const previous = state.rejected.reasons.find((r) => r.reason === reason)
    const entry: RejectReason = { reason, count: (previous?.count ?? 0) + 1, lastRxTs: rxTs }
    state.rejected = {
      count: state.rejected.count + 1,
      reasons: [entry, ...reasons].slice(0, MAX_REJECT_REASONS),
    }
    touch()
  }

  function received(rxTs: number) {
    const cutoff = rxTs - RATE_WINDOW_MS
    const kept = state.rxTimes.filter((t) => t > cutoff)
    kept.push(rxTs)
    state.rxTimes = kept
    if (state.lastRxTs === null || rxTs > state.lastRxTs) state.lastRxTs = rxTs
  }

  function latency(rxTs: number, ts: number) {
    const cutoff = rxTs - LATENCY_WINDOW_MS
    const kept = state.latencies.filter((l) => l.rxTs > cutoff)
    kept.push({ rxTs, ms: rxTs - ts })
    state.latencies = kept
  }

  return {
    subscribe(listener) {
      listeners.add(listener)
      return () => {
        listeners.delete(listener)
      }
    },

    getSnapshot() {
      return snapshot
    },

    message(topicName, payload, rxTs) {
      const result = decode(topicName, payload)
      if (!result.ok) {
        reject(result.reason, rxTs)
        return
      }
      const msg = result.value
      received(rxTs)

      if (msg.kind === "ble") {
        const { addr, rssi, mfr, ts } = msg.payload
        const previous: HeardDevice | undefined = state.heard[addr]
        const readings = previous ? previous.readings.slice(-(MAX_READINGS_PER_DEVICE - 1)) : []
        readings.push({ ts, rssi })
        state.heard = {
          ...state.heard,
          [addr]: {
            addr,
            mfr: mfr ?? previous?.mfr ?? null,
            count: (previous?.count ?? 0) + 1,
            lastTs: Math.max(ts, previous?.lastTs ?? 0),
            readings,
          },
        }
        state.counts = { ...state.counts, ble: state.counts.ble + 1 }
      } else if (msg.kind === "spectrum") {
        state.spectrum = msg.payload
        state.counts = { ...state.counts, spectrum: state.counts.spectrum + 1 }
        latency(rxTs, msg.payload.ts)
      } else {
        state.status = [{ ...msg.payload, rxTs }, ...state.status].slice(0, MAX_STATUS_ENTRIES)
        state.counts = { ...state.counts, status: state.counts.status + 1 }
        latency(rxTs, msg.payload.ts)
      }
      touch()
    },

    detection(d, rxTs) {
      const problem = detectionProblem(d)
      if (problem) {
        reject(`detection: ${problem}`, rxTs)
        return
      }
      const key = deviceKey(d)
      state.detections = { ...state.detections, [key]: d }
      state.counts = { ...state.counts, detection: state.counts.detection + 1 }

      // Allowed devices are tracked for the hall map but never raise an alert.
      if (d.type !== "allowed") {
        const existing = state.alerts.find((a) => a.id === key)
        if (existing) {
          const updated: Alert = {
            ...existing,
            type: d.type,
            band: d.band,
            typeConf: d.type_conf,
            bandConf: d.band_conf,
            rssi: d.rssi,
            lastTs: d.ts,
          }
          state.alerts = state.alerts.map((a) => (a.id === key ? updated : a))
        } else {
          const created: Alert = {
            id: key,
            node: d.node,
            addr: d.addr,
            type: d.type,
            band: d.band,
            typeConf: d.type_conf,
            bandConf: d.band_conf,
            rssi: d.rssi,
            firstTs: d.ts,
            lastTs: d.ts,
            latencyMs: rxTs - d.ts,
            state: "new",
          }
          state.alerts = [created, ...state.alerts]
        }
      }
      touch()
    },

    connection(next: ConnectionState) {
      state.connection = next
      touch()
    },

    setAlertState(id, next) {
      state.alerts = state.alerts.map((a) => (a.id === id ? { ...a, state: next } : a))
      touch()
    },

    reset() {
      state = emptyState(now())
      touch()
    },

    flush() {
      if (timer !== null) clearTimeout(timer)
      publish()
    },
  }
}
