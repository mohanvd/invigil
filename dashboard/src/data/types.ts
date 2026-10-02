import type { Result, SpectrumMessage, StatusMessage } from "./contract"

export const DEVICE_TYPES = ["phone", "earpiece", "smartwatch", "allowed"] as const
export type DeviceType = (typeof DEVICE_TYPES)[number]

export const BANDS = ["near", "mid", "far"] as const
export type Band = (typeof BANDS)[number]

/** Upper edge of each distance band in metres, from docs/data-protocol.md. */
export const BAND_EDGES_M: Record<Band, number> = { near: 1, mid: 2, far: 3.5 }

/**
 * One model output for one device over one decision window.
 * This is the payload proposed in docs/contract.md. It is not on MQTT yet,
 * so only the Demo source produces it.
 */
export interface Detection {
  ts: number
  node: string
  /** Hashed address, or null when the device was only seen in the spectrum scan. */
  addr: string | null
  type: DeviceType
  type_conf: number
  band: Band
  band_conf: number
  /** Median RSSI over the window in dBm, or null without BLE readings. */
  rssi: number | null
}

export type AlertState = "new" | "acknowledged" | "false_alarm"

/** One device the model flagged, kept up to date by later detections. */
export interface Alert {
  id: string
  node: string
  addr: string | null
  type: DeviceType
  band: Band
  typeConf: number
  bandConf: number
  rssi: number | null
  firstTs: number
  lastTs: number
  /** Unit to dashboard, for the detection that raised the alert. */
  latencyMs: number
  state: AlertState
}

export interface RssiReading {
  ts: number
  rssi: number
}

export interface HeardDevice {
  addr: string
  mfr: string | null
  count: number
  lastTs: number
  readings: RssiReading[]
}

export interface StatusEntry extends StatusMessage {
  rxTs: number
}

export interface RejectReason {
  reason: string
  count: number
  lastRxTs: number
}

export type ConnectionPhase = "idle" | "connecting" | "connected" | "reconnecting" | "error"

export interface ConnectionState {
  phase: ConnectionPhase
  /** Plain words for the user: why the connection is in this phase. */
  detail: string
}

export interface HallState {
  connection: ConnectionState
  /** Every device heard on BLE, by hashed address. */
  heard: Record<string, HeardDevice>
  spectrum: SpectrumMessage | null
  /** Status messages, newest first. */
  status: StatusEntry[]
  alerts: Alert[]
  /** Latest detection per device, including allowed ones. */
  detections: Record<string, Detection>
  counts: { ble: number; spectrum: number; status: number; detection: number }
  rejected: { count: number; reasons: RejectReason[] }
  /** Receive time of each recent message, oldest first. */
  rxTimes: number[]
  /** Unit to dashboard latency of recent spectrum and status messages. */
  latencies: { rxTs: number; ms: number }[]
  lastRxTs: number | null
  startedAt: number
}

export interface SessionSummary {
  name: string
  /** Start of the recording, ms since epoch. */
  startedAt: number
  durationS: number
  devices: number
  labelled: boolean
}

export type RequirementStatus = "pass" | "fail" | "pending"

export interface RequirementResult {
  id: 1 | 2 | 3 | 4 | 5 | 6
  /** Measured value in the requirement's unit, or null when not measured yet. */
  value: number | null
  note: string
}

export interface ConfusionMatrix<L extends string> {
  labels: readonly L[]
  /** counts[actual][predicted] */
  counts: number[][]
}

export interface RssiByDistancePoint {
  session: string
  type: DeviceType
  band: Band
  distanceM: number
  rssi: number
}

export interface ResultsReport {
  name: string
  generatedAt: number
  requirements: RequirementResult[]
  typeMatrix: ConfusionMatrix<DeviceType>
  bandMatrix: ConfusionMatrix<Band>
  rssiByDistance: RssiByDistancePoint[]
}

/** What a source pushes into the dashboard. */
export interface DataSink {
  /** One raw MQTT message. It is validated before anything is stored. */
  message(topic: string, payload: string, rxTs: number): void
  detection(detection: Detection, rxTs: number): void
  connection(state: ConnectionState): void
}

export type SourceKind = "demo" | "live"

/** The one interface every page reads through. Demo and Live both implement it. */
export interface DataSource {
  readonly kind: SourceKind
  start(sink: DataSink): void
  stop(): void
  /** null means this source cannot list sessions yet. */
  listSessions(): Promise<SessionSummary[] | null>
  /** null means no test run has been recorded. */
  loadResults(): Promise<ResultsReport | null>
}

export type { Result }
