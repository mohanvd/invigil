import type { Band, DeviceType } from "@/data/types"

// The near color means "within 1 m of the unit" and nothing else. not_near
// uses the far color. Every class name is written out in full so Tailwind can find it.
export const BAND_STYLE: Record<Band, { mark: string; soft: string; text: string; stroke: string; softVar: string }> = {
  near: { mark: "bg-near", soft: "bg-near-soft", text: "text-near", stroke: "var(--near)", softVar: "var(--near-soft)" },
  not_near: { mark: "bg-far", soft: "bg-far-soft", text: "text-far", stroke: "var(--far)", softVar: "var(--far-soft)" },
}

/** The band in words, as it is shown. */
export const BAND_LABEL: Record<Band, string> = {
  near: "near",
  not_near: "not near",
}

export const BAND_RANGE: Record<Band, string> = {
  near: "under 1 m",
  not_near: "1 m or more",
}

export const DEVICE_LABEL: Record<DeviceType, string> = {
  phone: "Phone",
  earpiece: "Earpiece",
  smartwatch: "Smartwatch",
  allowed: "Allowed",
}
