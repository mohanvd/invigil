// Demo data: one simulated unit (N1) in the 6-seat mini hall.
//
// This is a TypeScript port of the model in server/fake_publisher.py, so the
// Demo source and the fake publisher produce messages of the same shape. The
// data has the right shape, not the right physics: every constant below is the
// same placeholder guess the fake publisher uses, not a measurement.

import { NUM_CHANNELS, topic } from "../contract"
import type { BleMessage, SpectrumMessage, StatusMessage } from "../contract"
import type { Band, Detection, DeviceType } from "../types"
import { BAND_EDGES_M } from "../types"
import { createRng } from "./rng"
import type { Rng } from "./rng"

export const DEMO_NODE = "N1"
export const DEMO_FW = "0.1.0-demo"
export const SCAN_MS = 800
export const SEND_MS = 200
export const CYCLE_MS = SCAN_MS + SEND_MS
export const SWEEPS = 20
const STATUS_EVERY_CYCLES = 10
/** The model decides once per 5 s window (design requirement 1). */
const DETECT_EVERY_CYCLES = 5
/** Scan windows a device is on air before the first detection. */
const DETECT_AFTER_CYCLES = 3

const PATH_LOSS_EXP = 2.2
const PATH_LOSS_1M_DB = 40
const RSSI_NOISE_DB = 4
const BLE_SENSITIVITY_DBM = -92
const BLE_CATCH_RATE = 0.6
const RPD_THRESHOLD_DBM = -64
const BODY_LOSS_DB = 8
const HOP_BUSY = 0.015
const NOISE_HIT_RATE = 0.002
const WIFI_FIRST = 27
const WIFI_LAST = 47
const WIFI_BUSY = 0.25
const BT_FIRST = 2
const BT_LAST = 80
const MIN_DISTANCE_M = 0.3

export interface DemoDevice {
  label: string
  type: DeviceType
  /** Hashed address, or null for a device that never advertises. */
  addr: string | null
  mfr: string | null
  advIntervalMs: number | null
  advPhaseMs: number
  rssi1m: number
  audioTxDbm: number | null
  distanceM: number
  /** When the device switches on, in ms relative to the demo epoch. */
  onAtMs: number
}

export interface DemoCycle {
  messages: { topic: string; payload: string; rxTs: number }[]
  detections: { detection: Detection; rxTs: number }[]
}

export function bandOf(distanceM: number): Band {
  if (distanceM < BAND_EDGES_M.near) return "near"
  if (distanceM < BAND_EDGES_M.mid) return "mid"
  return "far"
}

function pathLossDb(distanceM: number): number {
  return 10 * PATH_LOSS_EXP * Math.log10(Math.max(distanceM, MIN_DISTANCE_M))
}

function either(p: number, q: number): number {
  return 1 - (1 - p) * (1 - q)
}

function clampRssi(value: number): number {
  return Math.max(-127, Math.min(0, Math.round(value)))
}

function median(values: number[]): number {
  const sorted = [...values].sort((a, b) => a - b)
  const mid = sorted.length >> 1
  return sorted.length % 2 ? sorted[mid] : (sorted[mid - 1] + sorted[mid]) / 2
}

function demoDevices(rng: Rng): DemoDevice[] {
  const devices: DemoDevice[] = [
    {
      label: "phone in a pocket",
      type: "phone",
      addr: rng.hex(12),
      mfr: "0x004C",
      advIntervalMs: 300,
      advPhaseMs: 0,
      rssi1m: -62,
      audioTxDbm: null,
      distanceM: 1.5,
      onAtMs: Number.NEGATIVE_INFINITY,
    },
    {
      // Silent on BLE while it streams, so only the spectrum scan sees it.
      label: "earpiece streaming audio",
      type: "earpiece",
      addr: null,
      mfr: null,
      advIntervalMs: null,
      advPhaseMs: 0,
      rssi1m: -68,
      audioTxDbm: 0,
      distanceM: 0.5,
      onAtMs: 8_000,
    },
    {
      label: "smartwatch on a wrist",
      type: "smartwatch",
      addr: rng.hex(12),
      mfr: "0x00E0",
      // Not a multiple of the scan cycle. An interval of exactly 1000 ms would
      // land on the same point of every cycle, and could sit in the send
      // window forever.
      advIntervalMs: 1285,
      advPhaseMs: 0,
      rssi1m: -64,
      audioTxDbm: null,
      distanceM: 3,
      onAtMs: -120_000,
    },
    {
      label: "proctor phone on the front desk",
      type: "allowed",
      addr: rng.hex(12),
      mfr: "0x0075",
      advIntervalMs: 500,
      advPhaseMs: 0,
      rssi1m: -59,
      audioTxDbm: null,
      distanceM: 2.5,
      onAtMs: Number.NEGATIVE_INFINITY,
    },
  ]
  for (const d of devices) {
    if (d.advIntervalMs !== null) d.advPhaseMs = rng.uniform(0, d.advIntervalMs)
  }
  return devices
}

export interface DemoGenerator {
  readonly devices: readonly DemoDevice[]
  /** Everything the unit and the model produce for the scan window that starts at scanStart. */
  cycle(scanStart: number): DemoCycle
}

/**
 * The same seed and the same sequence of scan windows always give the same
 * messages. Call cycle() with scan starts one CYCLE_MS apart, in order.
 */
export function createDemoGenerator(seed: number, epoch: number): DemoGenerator {
  const rng = createRng(seed)
  const devices = demoDevices(rng)
  const bootMs = epoch - 37 * 60_000
  const windows = new Map<DemoDevice, number[][]>()
  let cycles = 0

  function spectrumHits(t1: number): number[] {
    const p = new Array<number>(NUM_CHANNELS).fill(NOISE_HIT_RATE)
    for (let c = WIFI_FIRST; c <= WIFI_LAST; c++) p[c] = either(p[c], WIFI_BUSY)
    for (const dev of devices) {
      if (dev.audioTxDbm === null || t1 - epoch < dev.onAtMs) continue
      const rxDbm = dev.audioTxDbm - BODY_LOSS_DB - PATH_LOSS_1M_DB - pathLossDb(dev.distanceM)
      const above = 1 / (1 + Math.exp(-(rxDbm - RPD_THRESHOLD_DBM) / 3))
      for (let c = BT_FIRST; c <= BT_LAST; c++) {
        // Adaptive frequency hopping steers the link away from the Wi-Fi block.
        if (c >= WIFI_FIRST && c <= WIFI_LAST) continue
        p[c] = either(p[c], HOP_BUSY * above)
      }
    }
    return p.map((pc) => {
      let hits = 0
      for (let s = 0; s < SWEEPS; s++) if (rng.next() < pc) hits++
      return hits
    })
  }

  function cycle(scanStart: number): DemoCycle {
    const t0 = scanStart
    const t1 = scanStart + SCAN_MS
    const rxTs = t1 + Math.round(rng.uniform(60, 300))
    const out: DemoCycle = { messages: [], detections: [] }

    const ble: BleMessage[] = []
    for (const dev of devices) {
      const heard: number[] = []
      const on = t0 - epoch >= dev.onAtMs
      if (on && dev.advIntervalMs !== null && dev.addr !== null) {
        let k = Math.ceil((t0 - dev.advPhaseMs) / dev.advIntervalMs)
        for (;;) {
          const t = dev.advPhaseMs + k * dev.advIntervalMs + rng.uniform(0, 10)
          if (t >= t1) break
          k++
          const rssi = dev.rssi1m - pathLossDb(dev.distanceM) + rng.gauss(0, RSSI_NOISE_DB)
          if (rssi < BLE_SENSITIVITY_DBM || rng.next() > BLE_CATCH_RATE) continue
          const reading = clampRssi(rssi)
          heard.push(reading)
          ble.push({ ts: Math.floor(t), node: DEMO_NODE, addr: dev.addr, rssi: reading, mfr: dev.mfr })
        }
      }
      const recent = windows.get(dev) ?? []
      recent.push(heard)
      windows.set(dev, recent.slice(-DETECT_EVERY_CYCLES))
    }
    ble.sort((a, b) => a.ts - b.ts)
    for (const m of ble) {
      out.messages.push({ topic: topic(DEMO_NODE, "ble"), payload: JSON.stringify(m), rxTs })
    }

    const spectrum: SpectrumMessage = { ts: t1, node: DEMO_NODE, sweeps: SWEEPS, hits: spectrumHits(t1) }
    out.messages.push({ topic: topic(DEMO_NODE, "spectrum"), payload: JSON.stringify(spectrum), rxTs })

    if (cycles % STATUS_EVERY_CYCLES === 0) {
      const status: StatusMessage = {
        ts: t1,
        node: DEMO_NODE,
        uptime_s: Math.floor((t1 - bootMs) / 1000),
        wifi_rssi: clampRssi(-55 + rng.gauss(0, 2)),
        fw: DEMO_FW,
      }
      out.messages.push({ topic: topic(DEMO_NODE, "status"), payload: JSON.stringify(status), rxTs })
    }
    cycles++

    for (const dev of devices) {
      const onForMs = t0 - epoch - dev.onAtMs
      if (onForMs < 0) continue
      // A device that was on before the demo started is phased from the epoch.
      const base = Number.isFinite(onForMs) ? onForMs : t0 - epoch + 3_600_000
      const cyclesOn = Math.floor(base / CYCLE_MS) + 1
      if (cyclesOn < DETECT_AFTER_CYCLES) continue
      if ((cyclesOn - DETECT_AFTER_CYCLES) % DETECT_EVERY_CYCLES !== 0) continue

      const readings = (windows.get(dev) ?? []).flat()
      out.detections.push({
        rxTs,
        detection: {
          ts: t1,
          node: DEMO_NODE,
          addr: dev.addr,
          type: dev.type,
          type_conf: Math.round(rng.uniform(0.8, 0.97) * 100) / 100,
          band: bandOf(dev.distanceM),
          band_conf: Math.round(rng.uniform(0.72, 0.95) * 100) / 100,
          rssi: readings.length > 0 ? Math.round(median(readings)) : null,
        },
      })
    }

    return out
  }

  return { devices, cycle }
}
