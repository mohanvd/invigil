import { afterEach, describe, expect, it, vi } from "vitest"

import { effectiveSource, isDemoOnly } from "../build"

afterEach(() => {
  vi.unstubAllEnvs()
  vi.resetModules()
})

describe("VITE_DEMO_ONLY", () => {
  it("is off unless the value is exactly true", () => {
    expect(isDemoOnly({})).toBe(false)
    expect(isDemoOnly({ VITE_DEMO_ONLY: "" })).toBe(false)
    expect(isDemoOnly({ VITE_DEMO_ONLY: "false" })).toBe(false)
    expect(isDemoOnly({ VITE_DEMO_ONLY: "1" })).toBe(false)
    expect(isDemoOnly({ VITE_DEMO_ONLY: "TRUE" })).toBe(false)
    expect(isDemoOnly({ VITE_DEMO_ONLY: "true" })).toBe(true)
  })

  it("forces the Demo source when on, even if Live was saved in Settings", () => {
    expect(effectiveSource("live", true)).toBe("demo")
    expect(effectiveSource("demo", true)).toBe("demo")
  })

  it("changes nothing when off", () => {
    expect(effectiveSource("live", false)).toBe("live")
    expect(effectiveSource("demo", false)).toBe("demo")
  })

  it("reads the flag from the build environment", async () => {
    expect((await import("../build")).DEMO_ONLY).toBe(false)

    vi.resetModules()
    vi.stubEnv("VITE_DEMO_ONLY", "true")
    expect((await import("../build")).DEMO_ONLY).toBe(true)
  })
})
