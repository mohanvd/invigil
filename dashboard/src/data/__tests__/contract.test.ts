import { describe, expect, it } from "vitest"

import { decode, parseTopic, validate } from "../contract"

const TS = 1_727_340_000_123
const ble = () => ({ ts: TS, node: "N1", addr: "a91f03c2d4e8", rssi: -58, mfr: "0x004C" as string | null })
const spectrum = () => ({ ts: TS, node: "N1", sweeps: 50, hits: new Array<number>(126).fill(0) })
const status = () => ({ ts: TS, node: "N1", uptime_s: 3600, wifi_rssi: -61, fw: "0.1.0" })

function reason(result: { ok: boolean; reason?: string }): string {
  return result.ok ? "" : (result.reason ?? "")
}

describe("parseTopic", () => {
  it("splits a contract topic", () => {
    expect(parseTopic("invigil/node/N1/ble")).toEqual({ ok: true, value: { node: "N1", kind: "ble" } })
  })

  it.each([
    "invigil/node/N1",
    "invigil/node/N1/ble/extra",
    "other/node/N1/ble",
    "invigil/node/N9/ble",
    "invigil/node/N1/detection",
    "invigil/node/N1/toString",
  ])("rejects %s", (name) => {
    expect(parseTopic(name).ok).toBe(false)
  })
})

describe("validate", () => {
  it("accepts the three examples from docs/contract.md", () => {
    expect(validate("ble", ble(), "N1").ok).toBe(true)
    expect(validate("spectrum", spectrum(), "N1").ok).toBe(true)
    expect(validate("status", status(), "N1").ok).toBe(true)
  })

  it("accepts a null manufacturer", () => {
    expect(validate("ble", { ...ble(), mfr: null }).ok).toBe(true)
  })

  it("rejects payloads that are not objects", () => {
    for (const payload of [null, 5, "x", [ble()]]) {
      expect(reason(validate("ble", payload))).toBe("payload must be a JSON object")
    }
  })

  it("rejects missing and extra fields", () => {
    const missing: Record<string, unknown> = ble()
    delete missing.rssi
    expect(reason(validate("ble", missing))).toBe("missing field(s): rssi")
    expect(reason(validate("ble", { ...ble(), name: "x" }))).toBe("unexpected field(s): name")
  })

  it("rejects a raw MAC, uppercase hex and a short hash", () => {
    for (const addr of ["A9:1F:03:C2:D4:E8", "A91F03C2D4E8", "a91f03c2d4e", "a91f03c2d4e8f", 123]) {
      expect(reason(validate("ble", { ...ble(), addr }))).toMatch(/hashed address/)
    }
  })

  it("never echoes a rejected value", () => {
    const result = validate("ble", { ...ble(), addr: "A9:1F:03:C2:D4:E8" })
    expect(reason(result)).not.toContain("A9:1F")
  })

  it("rejects ts in seconds, in microseconds, and as a decimal", () => {
    expect(reason(validate("ble", { ...ble(), ts: 1_727_340_000 }))).toMatch(/too small/)
    expect(reason(validate("ble", { ...ble(), ts: TS * 1000 }))).toMatch(/out of range/)
    expect(reason(validate("ble", { ...ble(), ts: TS + 0.5 }))).toBe("ts must be an integer")
  })

  it("rejects an rssi that is out of range or not an integer", () => {
    expect(validate("ble", { ...ble(), rssi: 1 }).ok).toBe(false)
    expect(validate("ble", { ...ble(), rssi: -128 }).ok).toBe(false)
    expect(validate("ble", { ...ble(), rssi: -58.5 }).ok).toBe(false)
    expect(validate("ble", { ...ble(), rssi: true }).ok).toBe(false)
    expect(validate("ble", { ...ble(), rssi: "-58" }).ok).toBe(false)
  })

  it("rejects a malformed manufacturer ID", () => {
    for (const mfr of ["0x004c", "004C", "0x4C", 76]) {
      expect(validate("ble", { ...ble(), mfr }).ok).toBe(false)
    }
  })

  it("requires exactly 126 hit counts between 0 and sweeps", () => {
    expect(reason(validate("spectrum", { ...spectrum(), hits: new Array(125).fill(0) }))).toMatch(/126/)
    expect(reason(validate("spectrum", { ...spectrum(), hits: new Array(127).fill(0) }))).toMatch(/126/)
    expect(validate("spectrum", { ...spectrum(), hits: "0".repeat(126) }).ok).toBe(false)

    const tooMany = spectrum()
    tooMany.hits[7] = 51
    expect(reason(validate("spectrum", tooMany))).toMatch(/0 to sweeps/)

    const negative = spectrum()
    negative.hits[0] = -1
    expect(validate("spectrum", negative).ok).toBe(false)

    const decimal = spectrum()
    decimal.hits[0] = 0.5
    expect(validate("spectrum", decimal).ok).toBe(false)
  })

  it("rejects zero sweeps", () => {
    expect(validate("spectrum", { ...spectrum(), sweeps: 0 }).ok).toBe(false)
  })

  it("checks the status fields", () => {
    expect(validate("status", { ...status(), uptime_s: -1 }).ok).toBe(false)
    expect(validate("status", { ...status(), wifi_rssi: 5 }).ok).toBe(false)
    expect(validate("status", { ...status(), fw: "" }).ok).toBe(false)
    expect(validate("status", { ...status(), fw: "x".repeat(33) }).ok).toBe(false)
  })

  it("rejects an unknown node and a node that does not match the topic", () => {
    expect(reason(validate("ble", { ...ble(), node: "N2" }))).toMatch(/node must be one of/)
    expect(reason(validate("status", status(), "N2"))).toMatch(/does not match/)
  })
})

describe("decode", () => {
  it("returns the typed message", () => {
    const result = decode("invigil/node/N1/ble", JSON.stringify(ble()))
    expect(result).toEqual({ ok: true, value: { kind: "ble", node: "N1", payload: ble() } })
  })

  it("never throws on bad JSON", () => {
    expect(reason(decode("invigil/node/N1/ble", "{not json"))).toBe("payload is not valid JSON")
    expect(decode("invigil/node/N1/ble", "").ok).toBe(false)
  })

  it("rejects a bad topic before reading the payload", () => {
    expect(reason(decode("invigil/other", "{not json"))).toMatch(/topic is not/)
  })
})
