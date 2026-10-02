import type { RequirementResult, RequirementStatus } from "./types"

export interface Requirement {
  id: RequirementResult["id"]
  title: string
  /** The target, written the way the design requirements state it. */
  target: string
  limit: number
  /** "max": the value must not exceed the limit. "min": it must reach it. */
  kind: "max" | "min"
  unit: string
  decimals: number
}

/** The six design requirements. Tests measure exactly these. */
export const REQUIREMENTS: readonly Requirement[] = [
  { id: 1, title: "Response time", target: "at most 5 s", limit: 5, kind: "max", unit: "s", decimals: 1 },
  { id: 2, title: "Device type accuracy", target: "at least 85%", limit: 85, kind: "min", unit: "%", decimals: 1 },
  { id: 3, title: "Distance band accuracy", target: "at least 80%", limit: 80, kind: "min", unit: "%", decimals: 1 },
  { id: 4, title: "Alert latency", target: "within 2 s", limit: 2, kind: "max", unit: "s", decimals: 2 },
  { id: 5, title: "False alarms", target: "at most 1 per hour", limit: 1, kind: "max", unit: "per hour", decimals: 1 },
  { id: 6, title: "Detection range", target: "at least 3 m", limit: 3, kind: "min", unit: "m", decimals: 1 },
]

export function requirementStatus(requirement: Requirement, value: number | null): RequirementStatus {
  if (value === null) return "pending"
  const met = requirement.kind === "max" ? value <= requirement.limit : value >= requirement.limit
  return met ? "pass" : "fail"
}
