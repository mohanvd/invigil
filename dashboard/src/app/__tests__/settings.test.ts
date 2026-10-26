import { describe, expect, it } from "vitest"

import { DEFAULT_SETTINGS, settingsFromQuery } from "../settings"

describe("settings from the page URL", () => {
  it("does nothing without the launcher's parameters", () => {
    expect(settingsFromQuery("", DEFAULT_SETTINGS)).toBeNull()
    expect(settingsFromQuery("?foo=bar", DEFAULT_SETTINGS)).toBeNull()
  })

  it("switches to Live with the broker and username the launcher passes", () => {
    const search = "?" + new URLSearchParams({ source: "live", broker: "ws://localhost:9001", user: "invigil" })
    expect(settingsFromQuery(search, DEFAULT_SETTINGS)).toEqual({
      ...DEFAULT_SETTINGS,
      source: "live",
      brokerUrl: "ws://localhost:9001",
      username: "invigil",
    })
  })

  it("keeps the current value for anything malformed", () => {
    const current = { ...DEFAULT_SETTINGS, brokerUrl: "ws://laptop:9001" }
    const next = settingsFromQuery("?source=cloud&broker=http://example.com", current)
    expect(next?.source).toBe(current.source)
    expect(next?.brokerUrl).toBe("ws://laptop:9001")
  })

  it("never takes a password from the URL", () => {
    const next = settingsFromQuery("?source=live&password=secret", DEFAULT_SETTINGS)
    expect(JSON.stringify(next)).not.toContain("secret")
  })
})
