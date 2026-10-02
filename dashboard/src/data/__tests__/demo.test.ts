import { describe, expect, it } from "vitest"

import { decode } from "../contract"
import { demoResults, demoSessions } from "../demo/fixtures"
import { CYCLE_MS, createDemoGenerator } from "../demo/generator"
import { createDemoSource } from "../demo-source"
import { REQUIREMENTS, requirementStatus } from "../requirements"
import { createHallStore, detectionProblem } from "../store"

const EPOCH = 1_790_000_000_000

function run(seed: number, cycles: number) {
  const generator = createDemoGenerator(seed, EPOCH)
  const out = []
  for (let i = 0; i < cycles; i++) out.push(generator.cycle(EPOCH - 60_000 + i * CYCLE_MS))
  return out
}

describe("demo generator", () => {
  it("is deterministic for a seed", () => {
    expect(run(7, 90)).toEqual(run(7, 90))
    expect(run(7, 90)).not.toEqual(run(8, 90))
  })

  it("only produces messages that pass the contract", () => {
    const kinds = new Set<string>()
    for (const cycle of run(7, 120)) {
      for (const m of cycle.messages) {
        const result = decode(m.topic, m.payload)
        expect(result.ok).toBe(true)
        if (result.ok) kinds.add(result.value.kind)
      }
      for (const d of cycle.detections) expect(detectionProblem(d.detection)).toBeNull()
    }
    expect([...kinds].sort()).toEqual(["ble", "spectrum", "status"])
  })

  it("detects a device within 5 s of it switching on", () => {
    const generator = createDemoGenerator(7, EPOCH)
    const earpiece = generator.devices.find((d) => d.type === "earpiece")
    expect(earpiece).toBeDefined()
    let first: number | null = null
    for (let i = 0; i < 40 && first === null; i++) {
      const cycle = generator.cycle(EPOCH + i * CYCLE_MS)
      const hit = cycle.detections.find((d) => d.detection.type === "earpiece")
      if (hit) first = hit.detection.ts
    }
    expect(first).not.toBeNull()
    expect((first ?? 0) - (EPOCH + (earpiece?.onAtMs ?? 0))).toBeLessThanOrEqual(5000)
  })
})

describe("demo source", () => {
  it("backfills history through the same validated path as live data", () => {
    const store = createHallStore({ now: () => EPOCH, notifyEveryMs: 0 })
    const source = createDemoSource({ now: () => EPOCH })
    source.start(store)
    source.stop()

    const state = store.getSnapshot()
    expect(state.connection.phase).toBe("connected")
    expect(state.rejected.count).toBe(0)
    expect(state.counts.spectrum).toBeGreaterThan(150)
    expect(state.counts.status).toBeGreaterThan(10)
    expect(state.spectrum?.hits).toHaveLength(126)
    // Phone and smartwatch are on before the page opens; the earpiece is not yet.
    expect(state.alerts.map((a) => a.type).sort()).toEqual(["phone", "smartwatch"])
  })

  it("serves sessions and results that agree with each other", async () => {
    const source = createDemoSource()
    const sessions = await source.listSessions()
    const results = await source.loadResults()
    expect(sessions?.length).toBeGreaterThan(20)
    expect(sessions?.some((s) => !s.labelled)).toBe(true)
    expect(new Set(sessions?.map((s) => s.name)).size).toBe(sessions?.length)
    expect(demoSessions()).toEqual(sessions)

    expect(results?.requirements.map((r) => r.id)).toEqual([1, 2, 3, 4, 5, 6])
    const labelled = new Set(sessions?.filter((s) => s.labelled).map((s) => s.name))
    for (const point of results?.rssiByDistance ?? []) expect(labelled.has(point.session)).toBe(true)
    expect(demoResults()).toEqual(results)
  })
})

describe("requirements", () => {
  it("judges a value against its target", () => {
    const [response, typeAccuracy] = REQUIREMENTS
    expect(requirementStatus(response, null)).toBe("pending")
    expect(requirementStatus(response, 5)).toBe("pass")
    expect(requirementStatus(response, 5.1)).toBe("fail")
    expect(requirementStatus(typeAccuracy, 85)).toBe("pass")
    expect(requirementStatus(typeAccuracy, 84.9)).toBe("fail")
  })
})
