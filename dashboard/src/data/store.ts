import { decode, detectionFieldProblem } from "./contract"
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

export const MAX_READINGS_PER_DEVICE = 600
export const MAX_STATUS_ENTRIES = 50
export const MAX_REJECT_REASONS = 20
export const RATE_WINDOW_MS = 10_000
export const LATENCY_WINDOW_MS = 60_000

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

/** Check a detection against the detection topic in docs/contract.md. */
export function detectionProblem(d: Detection): string | null {
  if (!Number.isInteger(d.ts)) return "ts must be an integer"
  return detectionFieldProblem(d as unknown as Record<string, unknown>)
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

  function addDetection(d: Detection, rxTs: number) {
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
        // One message carries a whole scan window. Each reading counts on its own.
        const heard = { ...state.heard }
        for (const { addr, rssi, mfr, ts } of msg.payload.readings) {
          const previous: HeardDevice | undefined = heard[addr]
          const readings = previous ? previous.readings.slice(-(MAX_READINGS_PER_DEVICE - 1)) : []
          readings.push({ ts, rssi })
          heard[addr] = {
            addr,
            mfr: mfr ?? previous?.mfr ?? null,
            count: (previous?.count ?? 0) + 1,
            lastTs: Math.max(ts, previous?.lastTs ?? 0),
            readings,
          }
        }
        state.heard = heard
        state.counts = { ...state.counts, ble: state.counts.ble + msg.payload.readings.length }
      } else if (msg.kind === "detection") {
        addDetection(msg.payload, rxTs)
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
      addDetection(d, rxTs)
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
