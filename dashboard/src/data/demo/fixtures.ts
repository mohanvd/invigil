// Demo sessions and a demo results report. Both are generated from a fixed
// seed, follow the naming and matrix in docs/data-protocol.md, and exist only
// so the Sessions and Results pages can be checked before real data exists.

import type {
  Band,
  DeviceType,
  RequirementResult,
  ResultsReport,
  RssiByDistancePoint,
  SessionSummary,
} from "../types"
import { createRng } from "./rng"

const RECORD_AT_M: Record<Band, number> = { near: 0.5, mid: 1.5, far: 3 }
const RSSI_1M: Record<DeviceType, number> = { phone: -62, earpiece: -68, smartwatch: -64, allowed: -59 }
const STATES: Record<DeviceType, string[]> = {
  phone: ["idle", "screen-on"],
  earpiece: ["idle", "streaming"],
  smartwatch: ["wrist"],
  allowed: ["normal"],
}
const TYPES: DeviceType[] = ["phone", "earpiece", "smartwatch", "allowed"]
const BAND_ORDER: Band[] = ["near", "mid", "far"]
const FIRST_DAY = Date.UTC(2026, 8, 21, 7, 30)
const UNLABELLED = 4

interface DemoSession extends SessionSummary {
  point: RssiByDistancePoint | null
}

function isoDay(ms: number): string {
  return new Date(ms).toISOString().slice(0, 10)
}

function buildSessions(): DemoSession[] {
  const rng = createRng(12323)
  const sessions: DemoSession[] = []
  let day = 0
  let slot = 0

  function startOf(): number {
    return FIRST_DAY + day * 86_400_000 + slot * 5 * 60_000
  }

  for (let repeat = 1; repeat <= 2; repeat++) {
    // Every recording day starts with an empty-room baseline.
    slot = 0
    const baselineStart = startOf()
    sessions.push({
      name: `${isoDay(baselineStart)}-baseline-${repeat}`,
      startedAt: baselineStart,
      durationS: 180 + Math.round(rng.uniform(0, 6)),
      devices: Math.round(rng.uniform(2, 4)),
      labelled: true,
      point: null,
    })
    slot++

    for (const type of TYPES) {
      for (const band of BAND_ORDER) {
        for (const state of STATES[type]) {
          const startedAt = startOf()
          const name = `${isoDay(startedAt)}-${type}-${band}-${state}-${repeat}`
          const distanceM = RECORD_AT_M[band]
          sessions.push({
            name,
            startedAt,
            durationS: 180 + Math.round(rng.uniform(0, 9)),
            // The test device plus whatever else was on air in the room.
            devices: 1 + Math.round(rng.uniform(2, 5)),
            labelled: true,
            point: {
              session: name,
              type,
              band,
              distanceM,
              rssi: Math.round(RSSI_1M[type] - 22 * Math.log10(distanceM) + rng.gauss(0, 2.5)),
            },
          })
          slot++
        }
      }
    }
    day += 2
  }

  // The most recent recordings are still waiting for a session.json.
  for (const s of sessions.slice(-UNLABELLED)) {
    s.labelled = false
    s.point = null
  }
  return sessions
}

const SESSIONS = buildSessions()

export function demoSessions(): SessionSummary[] {
  return SESSIONS.map((s) => ({
    name: s.name,
    startedAt: s.startedAt,
    durationS: s.durationS,
    devices: s.devices,
    labelled: s.labelled,
  }))
}

function accuracy(counts: number[][]): number {
  let correct = 0
  let total = 0
  counts.forEach((row, i) =>
    row.forEach((n, j) => {
      total += n
      if (i === j) correct += n
    })
  )
  return (correct / total) * 100
}

export function demoResults(): ResultsReport {
  // counts[actual][predicted], in held-out windows.
  const typeCounts = [
    [151, 5, 13, 6],
    [7, 160, 5, 3],
    [18, 4, 149, 4],
    [22, 1, 5, 147],
  ]
  const bandCounts = [
    [214, 19, 0],
    [31, 168, 34],
    [3, 62, 168],
  ]

  const requirements: RequirementResult[] = [
    { id: 1, value: 3.4, note: "Longest time to first alert across the demo sessions." },
    { id: 2, value: accuracy(typeCounts), note: "From the device type confusion matrix below." },
    { id: 3, value: accuracy(bandCounts), note: "From the distance band confusion matrix below." },
    { id: 4, value: 0.31, note: "Median of receive time minus unit time." },
    { id: 5, value: 0, note: "Alerts raised during the empty-room baselines." },
    { id: 6, value: null, note: "The range test has not been run." },
  ]

  return {
    name: "demo-train",
    generatedAt: SESSIONS[SESSIONS.length - 1].startedAt + 3_600_000,
    requirements,
    typeMatrix: { labels: TYPES, counts: typeCounts },
    bandMatrix: { labels: BAND_ORDER, counts: bandCounts },
    rssiByDistance: SESSIONS.flatMap((s) => (s.point ? [s.point] : [])),
  }
}
