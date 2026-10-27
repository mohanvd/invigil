import { describe, expect, it } from "vitest"

import { MAX_BLE_PAYLOAD_BYTES, decode, packBle, parseTopic, validate } from "../contract"
import type { BleReading } from "../contract"

const TS = 1_727_340_000_123
const reading = (): BleReading => ({ ts: TS, addr: "a91f03c2d4e8", rssi: -58, mfr: "0x004C" })
const ble = () => ({ ts: TS + 877, node: "N1", readings: [reading()] })
/** A ble message whose one reading has these changes. */
const bleWith = (changes: Record<string, unknown>) => ({ ...ble(), readings: [{ ...reading(), ...changes }] })
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
    expect(validate("ble", bleWith({ mfr: null })).ok).toBe(true)
  })

  it("rejects payloads that are not objects", () => {
    for (const payload of [null, 5, "x", [ble()]]) {
      expect(reason(validate("ble", payload))).toBe("payload must be a JSON object")
    }
  })

  it("rejects missing and extra fields", () => {
    const missing: Record<string, unknown> = ble()
    delete missing.readings
    expect(reason(validate("ble", missing))).toBe("missing field(s): readings")
    expect(reason(validate("ble", { ...ble(), name: "x" }))).toBe("unexpected field(s): name")
    const noRssi: Record<string, unknown> = { ...reading() }
    delete noRssi.rssi
    expect(reason(validate("ble", { ...ble(), readings: [noRssi] }))).toBe("reading is missing field(s): rssi")
    expect(reason(validate("ble", bleWith({ name: "x" })))).toBe("reading has unexpected field(s): name")
  })

  it("rejects the old one-reading shape", () => {
    const old = { ts: TS, node: "N1", addr: "a91f03c2d4e8", rssi: -58, mfr: "0x004C" }
    expect(validate("ble", old).ok).toBe(false)
  })

  it("accepts several readings and rejects an empty or malformed list", () => {
    const two = { ...ble(), readings: [reading(), { ...reading(), ts: TS + 300, addr: "0f5e2b7a91c4", mfr: null }] }
    expect(validate("ble", two, "N1").ok).toBe(true)
    for (const readings of [[], null, "x", [null], [[1, 2]]]) {
      expect(validate("ble", { ...ble(), readings }).ok).toBe(false)
    }
  })

  it("rejects the whole message when one reading is bad", () => {
    const mixed = { ...ble(), readings: [reading(), { ...reading(), rssi: 3 }] }
    expect(reason(validate("ble", mixed))).toBe("reading rssi is out of range -127..0")
  })

  it("rejects a raw MAC, uppercase hex and a short hash", () => {
    for (const addr of ["A9:1F:03:C2:D4:E8", "A91F03C2D4E8", "a91f03c2d4e", "a91f03c2d4e8f", 123]) {
      expect(reason(validate("ble", bleWith({ addr })))).toMatch(/hashed address/)
    }
  })

  it("never echoes a rejected value", () => {
    const result = validate("ble", bleWith({ addr: "A9:1F:03:C2:D4:E8" }))
    expect(reason(result)).not.toContain("A9:1F")
  })

  it("rejects ts in seconds, in microseconds, and as a decimal", () => {
    expect(reason(validate("ble", { ...ble(), ts: 1_727_340_000 }))).toMatch(/too small/)
    expect(reason(validate("ble", { ...ble(), ts: TS * 1000 }))).toMatch(/out of range/)
    expect(reason(validate("ble", { ...ble(), ts: TS + 0.5 }))).toBe("ts must be an integer")
    expect(reason(validate("ble", bleWith({ ts: 1_727_340_000 })))).toMatch(/reading ts is too small/)
    expect(reason(validate("ble", bleWith({ ts: TS * 1000 })))).toMatch(/out of range/)
    expect(reason(validate("ble", bleWith({ ts: TS + 0.5 })))).toBe("reading ts must be an integer")
  })

  it("rejects an rssi that is out of range or not an integer", () => {
    expect(validate("ble", bleWith({ rssi: 1 })).ok).toBe(false)
    expect(validate("ble", bleWith({ rssi: -128 })).ok).toBe(false)
    expect(validate("ble", bleWith({ rssi: -58.5 })).ok).toBe(false)
    expect(validate("ble", bleWith({ rssi: true })).ok).toBe(false)
    expect(validate("ble", bleWith({ rssi: "-58" })).ok).toBe(false)
  })

  it("rejects a malformed manufacturer ID", () => {
    for (const mfr of ["0x004c", "004C", "0x4C", 76]) {
      expect(validate("ble", bleWith({ mfr })).ok).toBe(false)
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

describe("packBle", () => {
  const bytes = (value: unknown) => new TextEncoder().encode(JSON.stringify(value)).length

  it("keeps order, stays under the size limit and uses as few messages as it can", () => {
    const readings: BleReading[] = Array.from({ length: 200 }, (_, i) => ({
      ts: TS + i,
      addr: "a91f03c2d4e8",
      rssi: -(i % 128),
      mfr: i % 3 ? null : "0x004C",
    }))
    const messages = packBle(TS + 1000, "N1", readings)
    expect(messages.length).toBeGreaterThan(1)
    expect(messages.flatMap((m) => m.readings)).toEqual(readings)
    for (const m of messages) {
      expect(validate("ble", m, "N1").ok).toBe(true)
      expect(bytes(m)).toBeLessThanOrEqual(MAX_BLE_PAYLOAD_BYTES)
    }
    for (let i = 0; i + 1 < messages.length; i++) {
      const bigger = { ...messages[i], readings: [...messages[i].readings, messages[i + 1].readings[0]] }
      expect(bytes(bigger)).toBeGreaterThan(MAX_BLE_PAYLOAD_BYTES)
    }
  })

  it("fits 19 worst-case readings in one message, as docs/contract.md says", () => {
    const worst: BleReading = { ts: 9_999_999_999_999, addr: "a91f03c2d4e8", rssi: -127, mfr: "0xFFFF" }
    expect(bytes(worst)).toBe(69)
    expect(packBle(9_999_999_999_999, "N1", new Array<BleReading>(40).fill(worst))[0].readings).toHaveLength(19)
  })

  it("sends nothing for no readings", () => {
    expect(packBle(TS, "N1", [])).toEqual([])
  })
})
