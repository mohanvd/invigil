// The Invigil MQTT contract, as the dashboard sees it.
//
// This mirrors server/contract.py field for field. If the contract changes,
// change docs/contract.md, server/contract.py and this file together.

export const TOPIC_ROOT = "invigil/node"
export const SUBSCRIPTION = `${TOPIC_ROOT}/+/+`
// One sensor unit for now. Phase 2 adds units here; the topic format stays the same.
export const NODE_IDS: readonly string[] = ["N1"]
export const NUM_CHANNELS = 126

// A value below MIN_TS_MS means the unit has not synced its clock, or it sent
// seconds instead of milliseconds. Above MAX_TS_MS usually means microseconds.
export const MIN_TS_MS = 1_600_000_000_000
export const MAX_TS_MS = 9_999_999_999_999

export interface BleMessage {
  ts: number
  node: string
  addr: string
  rssi: number
  mfr: string | null
}

export interface SpectrumMessage {
  ts: number
  node: string
  sweeps: number
  hits: number[]
}

export interface StatusMessage {
  ts: number
  node: string
  uptime_s: number
  wifi_rssi: number
  fw: string
}

export interface MessageByKind {
  ble: BleMessage
  spectrum: SpectrumMessage
  status: StatusMessage
}

export type Kind = keyof MessageByKind

export const FIELDS: { readonly [K in Kind]: readonly (keyof MessageByKind[K] & string)[] } = {
  ble: ["ts", "node", "addr", "rssi", "mfr"],
  spectrum: ["ts", "node", "sweeps", "hits"],
  status: ["ts", "node", "uptime_s", "wifi_rssi", "fw"],
}

export const KINDS = Object.keys(FIELDS) as Kind[]

export type ContractMessage = {
  [K in Kind]: { kind: K; node: string; payload: MessageByKind[K] }
}[Kind]

export type Result<T> = { ok: true; value: T } | { ok: false; reason: string }

const ADDR_RE = /^[0-9a-f]{12}$/
const MFR_RE = /^0x[0-9A-F]{4}$/

function fail(reason: string): { ok: false; reason: string } {
  return { ok: false, reason }
}

function isKind(value: string): value is Kind {
  return Object.hasOwn(FIELDS, value)
}

export function topic(node: string, kind: Kind): string {
  return `${TOPIC_ROOT}/${node}/${kind}`
}

/** Split "invigil/node/N1/ble" into the unit ID and the message kind. */
export function parseTopic(name: string): Result<{ node: string; kind: Kind }> {
  const parts = name.split("/")
  if (parts.length !== 4 || `${parts[0]}/${parts[1]}` !== TOPIC_ROOT) {
    return fail(`topic is not ${TOPIC_ROOT}/<node>/<kind>`)
  }
  const node = parts[2]
  const kind = parts[3]
  if (!NODE_IDS.includes(node)) return fail("unknown node in topic")
  if (!isKind(kind)) return fail("unknown kind in topic")
  return { ok: true, value: { node, kind } }
}

// Reasons name fields but never echo values, so a bad message cannot leak a
// raw address into the page.
function checkInt(
  payload: Record<string, unknown>,
  key: string,
  lo: number,
  hi: number
): string | null {
  const value = payload[key]
  if (typeof value !== "number" || !Number.isInteger(value)) {
    return `${key} must be an integer`
  }
  if (value < lo || value > hi) return `${key} is out of range ${lo}..${hi}`
  return null
}

/** Check a decoded JSON payload against the contract. */
export function validate<K extends Kind>(
  kind: K,
  payload: unknown,
  node?: string
): Result<MessageByKind[K]> {
  if (typeof payload !== "object" || payload === null || Array.isArray(payload)) {
    return fail("payload must be a JSON object")
  }
  const p = payload as Record<string, unknown>

  const expected: readonly string[] = FIELDS[kind]
  const missing = expected.filter((k) => !Object.hasOwn(p, k))
  if (missing.length > 0) return fail(`missing field(s): ${missing.join(", ")}`)
  const extra = Object.keys(p)
    .filter((k) => !expected.includes(k))
    .sort()
  if (extra.length > 0) return fail(`unexpected field(s): ${extra.join(", ")}`)

  const tsError = checkInt(p, "ts", 0, MAX_TS_MS)
  if (tsError) return fail(tsError)
  if ((p.ts as number) < MIN_TS_MS) {
    return fail("ts is too small: unit clock not synced, or seconds sent instead of ms")
  }
  if (typeof p.node !== "string" || !NODE_IDS.includes(p.node)) {
    return fail(`node must be one of ${NODE_IDS.join(", ")}`)
  }
  if (node !== undefined && p.node !== node) {
    return fail("node in payload does not match node in topic")
  }

  if (kind === "ble") {
    if (typeof p.addr !== "string" || !ADDR_RE.test(p.addr)) {
      return fail("addr must be a hashed address: 12 lowercase hex chars")
    }
    const rssiError = checkInt(p, "rssi", -127, 0)
    if (rssiError) return fail(rssiError)
    // null is allowed: many advertisements carry no manufacturer data.
    if (p.mfr !== null && (typeof p.mfr !== "string" || !MFR_RE.test(p.mfr))) {
      return fail('mfr must be null or a company ID like "0x004C"')
    }
  } else if (kind === "spectrum") {
    const sweepsError = checkInt(p, "sweeps", 1, 65_535)
    if (sweepsError) return fail(sweepsError)
    const hits = p.hits
    if (!Array.isArray(hits) || hits.length !== NUM_CHANNELS) {
      return fail(`hits must be a list of ${NUM_CHANNELS} integers`)
    }
    const sweeps = p.sweeps as number
    for (const h of hits) {
      if (typeof h !== "number" || !Number.isInteger(h) || h < 0 || h > sweeps) {
        return fail("each hit count must be an integer from 0 to sweeps")
      }
    }
  } else {
    const uptimeError = checkInt(p, "uptime_s", 0, 2 ** 31 - 1)
    if (uptimeError) return fail(uptimeError)
    const wifiError = checkInt(p, "wifi_rssi", -127, 0)
    if (wifiError) return fail(wifiError)
    if (typeof p.fw !== "string" || p.fw.length < 1 || p.fw.length > 32) {
      return fail("fw must be a version string of 1 to 32 chars")
    }
  }

  return { ok: true, value: p as unknown as MessageByKind[K] }
}

/** Parse and check one raw MQTT message. Never throws. */
export function decode(topicName: string, raw: string): Result<ContractMessage> {
  const parsed = parseTopic(topicName)
  if (!parsed.ok) return parsed
  const { node, kind } = parsed.value

  let json: unknown
  try {
    json = JSON.parse(raw)
  } catch {
    return fail("payload is not valid JSON")
  }

  const checked = validate(kind, json, node)
  if (!checked.ok) return checked
  return { ok: true, value: { kind, node, payload: checked.value } as ContractMessage }
}
