const two = (n: number) => String(n).padStart(2, "0")

/** 14:02:31, local time, 24 hour. */
export function formatClock(ts: number): string {
  const d = new Date(ts)
  return `${two(d.getHours())}:${two(d.getMinutes())}:${two(d.getSeconds())}`
}

/** 2026-10-20 14:02 */
export function formatDateTime(ts: number): string {
  const d = new Date(ts)
  return `${d.getFullYear()}-${two(d.getMonth() + 1)}-${two(d.getDate())} ${two(d.getHours())}:${two(d.getMinutes())}`
}

export function formatAgo(ms: number): string {
  const s = Math.max(0, Math.round(ms / 1000))
  if (s < 60) return `${s} s ago`
  const min = Math.floor(s / 60)
  if (min < 60) return `${min} min ago`
  return `${Math.floor(min / 60)} h ${two(min % 60)} min ago`
}

/** 3 min 04 s */
export function formatDuration(seconds: number): string {
  const s = Math.max(0, Math.round(seconds))
  if (s < 60) return `${s} s`
  const min = Math.floor(s / 60)
  if (min < 60) return `${min} min ${two(s % 60)} s`
  return `${Math.floor(min / 60)} h ${two(min % 60)} min`
}

export function formatDbm(rssi: number): string {
  return `${rssi} dBm`
}

export function formatPercent(fraction: number): string {
  return `${Math.round(fraction * 100)}%`
}
