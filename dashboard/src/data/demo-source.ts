import { demoResults, demoSessions } from "./demo/fixtures"
import { CYCLE_MS, SCAN_MS, createDemoGenerator } from "./demo/generator"
import type { DataSink, DataSource } from "./types"

export const DEMO_SEED = 12323
/** History generated on start, so the charts are not empty on the first frame. */
export const DEMO_BACKFILL_MS = 180_000
/** A window is delivered this long after its scan ends, like a real send window. */
const DELIVERY_MS = 300

export interface DemoOptions {
  seed?: number
  now?: () => number
}

/** Deterministic mock data that follows the MQTT contract. No network. */
export function createDemoSource(options: DemoOptions = {}): DataSource {
  const now = options.now ?? Date.now
  const seed = options.seed ?? DEMO_SEED
  let timer: ReturnType<typeof setInterval> | null = null

  return {
    kind: "demo",

    start(sink: DataSink) {
      const epoch = now()
      const generator = createDemoGenerator(seed, epoch)
      let scanStart = epoch - DEMO_BACKFILL_MS

      function catchUp() {
        while (scanStart + SCAN_MS + DELIVERY_MS <= now()) {
          const cycle = generator.cycle(scanStart)
          for (const m of cycle.messages) sink.message(m.topic, m.payload, m.rxTs)
          for (const d of cycle.detections) sink.detection(d.detection, d.rxTs)
          scanStart += CYCLE_MS
        }
      }

      sink.connection({ phase: "connected", detail: "Demo data, generated in the browser" })
      catchUp()
      timer = setInterval(catchUp, 250)
    },

    stop() {
      if (timer !== null) clearInterval(timer)
      timer = null
    },

    listSessions() {
      return Promise.resolve(demoSessions())
    },

    loadResults() {
      return Promise.resolve(demoResults())
    },
  }
}
