import { describe, expect, it } from "vitest"

import {
  activeAlertCount,
  alertLatencyP50,
  devicesHeard,
  falseAlarmsPerHour,
  isUnitOnline,
  mapDevices,
  messagesPerSecond,
  percentile,
  visibleAlerts,
} from "../selectors"
import { MAX_READINGS_PER_DEVICE, createHallStore, detectionProblem } from "../store"
import type { Detection } from "../types"

const T0 = 1_727_340_000_000

function makeStore() {
  return createHallStore({ now: () => T0, notifyEveryMs: 0 })
}

function ble(ts: number, addr = "a91f03c2d4e8", rssi = -58) {
  return JSON.stringify({ ts, node: "N1", addr, rssi, mfr: "0x004C" })
}

function detection(overrides: Partial<Detection> = {}): Detection {
  return {
    ts: T0,
    node: "N1",
    addr: "a91f03c2d4e8",
    type: "phone",
    type_conf: 0.9,
    band: "mid",
    band_conf: 0.8,
    rssi: -60,
    ...overrides,
  }
}

describe("message ingest", () => {
  it("stores a valid BLE reading under its hashed address", () => {
    const store = makeStore()
    store.message("invigil/node/N1/ble", ble(T0), T0 + 120)
    const state = store.getSnapshot()
    expect(state.counts.ble).toBe(1)
    expect(state.heard.a91f03c2d4e8.readings).toEqual([{ ts: T0, rssi: -58 }])
    expect(state.lastRxTs).toBe(T0 + 120)
  })

  it("drops and counts bad messages without throwing", () => {
    const store = makeStore()
    const bad: [string, string][] = [
      ["invigil/node/N1/ble", "{broken"],
      ["invigil/node/N1/ble", JSON.stringify({ ts: T0, node: "N1", addr: "A9:1F:03:C2:D4:E8", rssi: -58, mfr: null })],
      ["invigil/node/N1/spectrum", JSON.stringify({ ts: T0, node: "N1", sweeps: 20, hits: [1, 2, 3] })],
      ["invigil/node/N1/status", JSON.stringify({ ts: 1_727_340_000, node: "N1", uptime_s: 1, wifi_rssi: -60, fw: "0.1.0" })],
      ["invigil/node/N7/ble", ble(T0)],
      ["something/else", "{}"],
    ]
    for (const [topic, payload] of bad) {
      expect(() => store.message(topic, payload, T0)).not.toThrow()
    }
    const state = store.getSnapshot()
    expect(state.rejected.count).toBe(bad.length)
    expect(state.counts).toEqual({ ble: 0, spectrum: 0, status: 0, detection: 0 })
    expect(state.heard).toEqual({})
    expect(state.lastRxTs).toBeNull()
  })

  it("groups repeated rejections by reason", () => {
    const store = makeStore()
    store.message("invigil/node/N1/ble", "{broken", T0)
    store.message("invigil/node/N1/ble", "{broken", T0 + 1)
    const { rejected } = store.getSnapshot()
    expect(rejected.count).toBe(2)
    expect(rejected.reasons).toEqual([{ reason: "payload is not valid JSON", count: 2, lastRxTs: T0 + 1 }])
  })

  it("caps the readings kept per device", () => {
    const store = makeStore()
    for (let i = 0; i < MAX_READINGS_PER_DEVICE + 25; i++) {
      store.message("invigil/node/N1/ble", ble(T0 + i), T0 + i)
    }
    const device = store.getSnapshot().heard.a91f03c2d4e8
    expect(device.readings).toHaveLength(MAX_READINGS_PER_DEVICE)
    expect(device.count).toBe(MAX_READINGS_PER_DEVICE + 25)
    expect(device.readings.at(-1)?.ts).toBe(T0 + MAX_READINGS_PER_DEVICE + 24)
  })

  it("keeps status messages newest first and records latency", () => {
    const store = makeStore()
    const status = (ts: number) => JSON.stringify({ ts, node: "N1", uptime_s: 10, wifi_rssi: -61, fw: "0.1.0" })
    store.message("invigil/node/N1/status", status(T0), T0 + 200)
    store.message("invigil/node/N1/status", status(T0 + 10_000), T0 + 10_400)
    const state = store.getSnapshot()
    expect(state.status.map((s) => s.ts)).toEqual([T0 + 10_000, T0])
    expect(state.latencies.map((l) => l.ms)).toEqual([200, 400])
  })

  it("notifies subscribers with a new snapshot", () => {
    const store = makeStore()
    const before = store.getSnapshot()
    let calls = 0
    const unsubscribe = store.subscribe(() => calls++)
    store.message("invigil/node/N1/ble", ble(T0), T0)
    expect(calls).toBe(1)
    expect(store.getSnapshot()).not.toBe(before)
    unsubscribe()
    store.message("invigil/node/N1/ble", ble(T0 + 1), T0 + 1)
    expect(calls).toBe(1)
  })
})

describe("detections and alerts", () => {
  it("raises one alert per device and updates it", () => {
    const store = makeStore()
    store.detection(detection(), T0 + 300)
    store.detection(detection({ ts: T0 + 5000, band: "near", rssi: -48 }), T0 + 5200)
    const { alerts } = store.getSnapshot()
    expect(alerts).toHaveLength(1)
    expect(alerts[0]).toMatchObject({
      band: "near",
      rssi: -48,
      firstTs: T0,
      lastTs: T0 + 5000,
      latencyMs: 300,
      state: "new",
    })
  })

  it("keys a spectrum-only device without an address", () => {
    const store = makeStore()
    store.detection(detection({ addr: null, type: "earpiece", rssi: null }), T0)
    expect(store.getSnapshot().alerts[0].id).toBe("N1:spectrum:earpiece")
  })

  it("tracks an allowed device without raising an alert", () => {
    const store = makeStore()
    store.detection(detection({ type: "allowed" }), T0)
    const state = store.getSnapshot()
    expect(state.alerts).toHaveLength(0)
    expect(Object.keys(state.detections)).toEqual(["a91f03c2d4e8"])
  })

  it("drops a malformed detection", () => {
    const store = makeStore()
    store.detection(detection({ addr: "A9:1F:03:C2:D4:E8" }), T0)
    store.detection(detection({ type_conf: 1.4 }), T0)
    const state = store.getSnapshot()
    expect(state.alerts).toHaveLength(0)
    expect(state.rejected.count).toBe(2)
    expect(detectionProblem(detection())).toBeNull()
  })

  it("acknowledges and marks false alarms", () => {
    const store = makeStore()
    store.detection(detection(), T0)
    store.detection(detection({ addr: "0123456789ab", type: "smartwatch" }), T0)
    store.setAlertState("a91f03c2d4e8", "acknowledged")
    store.setAlertState("0123456789ab", "false_alarm")
    const state = store.getSnapshot()
    expect(activeAlertCount(state.alerts, [])).toBe(0)
    expect(falseAlarmsPerHour(state, T0 + 1_800_000)).toBe(2)
  })
})

describe("selectors", () => {
  it("computes percentiles", () => {
    expect(percentile([], 50)).toBeNull()
    expect(percentile([300], 50)).toBe(300)
    expect(percentile([100, 200, 300, 400], 50)).toBe(250)
  })

  it("counts devices heard in the last minute", () => {
    const store = makeStore()
    store.message("invigil/node/N1/ble", ble(T0, "aaaaaaaaaaaa"), T0)
    store.message("invigil/node/N1/ble", ble(T0 + 90_000, "bbbbbbbbbbbb"), T0 + 90_000)
    const heard = devicesHeard(store.getSnapshot(), T0 + 100_000)
    expect(heard.map((d) => d.addr)).toEqual(["bbbbbbbbbbbb"])
  })

  it("reports the unit offline after 15 s of silence", () => {
    const store = makeStore()
    expect(isUnitOnline(store.getSnapshot(), T0)).toBe(false)
    store.message("invigil/node/N1/ble", ble(T0), T0)
    expect(isUnitOnline(store.getSnapshot(), T0 + 14_000)).toBe(true)
    expect(isUnitOnline(store.getSnapshot(), T0 + 16_000)).toBe(false)
  })

  it("measures the message rate over the last 10 s", () => {
    const store = makeStore()
    for (let i = 0; i < 20; i++) store.message("invigil/node/N1/ble", ble(T0 + i * 500), T0 + i * 500)
    expect(messagesPerSecond(store.getSnapshot(), T0 + 9_500)).toBe(2)
  })

  it("filters alerts and hides whitelisted devices", () => {
    const store = makeStore()
    store.detection(detection(), T0)
    store.detection(detection({ addr: "0123456789ab", type: "smartwatch", band: "far", ts: T0 + 1000 }), T0 + 1000)
    const { alerts } = store.getSnapshot()
    const all = { type: "all", band: "all" } as const

    expect(visibleAlerts(alerts, [], all).map((a) => a.id)).toEqual(["0123456789ab", "a91f03c2d4e8"])
    expect(visibleAlerts(alerts, [], { type: "phone", band: "all" })).toHaveLength(1)
    expect(visibleAlerts(alerts, [], { type: "all", band: "far" })).toHaveLength(1)
    expect(visibleAlerts(alerts, [{ addr: "a91f03c2d4e8", label: "Proctor phone" }], all)).toHaveLength(1)
    expect(alertLatencyP50(alerts)).toBe(0)
  })

  it("puts recent devices on the map and shows whitelisted ones as allowed", () => {
    const store = makeStore()
    store.detection(detection(), T0)
    store.detection(detection({ addr: "0123456789ab", ts: T0 - 60_000 }), T0)
    const devices = mapDevices(store.getSnapshot(), [{ addr: "a91f03c2d4e8", label: "Proctor phone" }], T0 + 1000)
    expect(devices).toEqual([
      { key: "a91f03c2d4e8", addr: "a91f03c2d4e8", type: "allowed", band: "mid", label: "Proctor phone" },
    ])
  })
})
