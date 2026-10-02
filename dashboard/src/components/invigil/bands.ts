import type { Band, DeviceType } from "@/data/types"

// near, mid and far colors mean a distance band and nothing else. Every class
// name is written out in full so Tailwind can find it.
export const BAND_STYLE: Record<Band, { mark: string; soft: string; text: string; stroke: string; softVar: string }> = {
  near: { mark: "bg-near", soft: "bg-near-soft", text: "text-near", stroke: "var(--near)", softVar: "var(--near-soft)" },
  mid: { mark: "bg-mid", soft: "bg-mid-soft", text: "text-mid", stroke: "var(--mid)", softVar: "var(--mid-soft)" },
  far: { mark: "bg-far", soft: "bg-far-soft", text: "text-far", stroke: "var(--far)", softVar: "var(--far-soft)" },
}

export const BAND_RANGE: Record<Band, string> = {
  near: "under 1 m",
  mid: "1 to 2 m",
  far: "2 to 3.5 m",
}

export const DEVICE_LABEL: Record<DeviceType, string> = {
  phone: "Phone",
  earpiece: "Earpiece",
  smartwatch: "Smartwatch",
  allowed: "Allowed",
}
