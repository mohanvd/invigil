// Browser storage can be blocked or full. Reads fall back, writes fail quietly.

export function readJson(storage: Storage, key: string): unknown {
  try {
    const raw = storage.getItem(key)
    return raw === null ? null : JSON.parse(raw)
  } catch {
    return null
  }
}

export function writeJson(storage: Storage, key: string, value: unknown): void {
  try {
    storage.setItem(key, JSON.stringify(value))
  } catch {
    // Nothing to do: the setting still applies for this page view.
  }
}

export function readString(storage: Storage, key: string): string | null {
  try {
    return storage.getItem(key)
  } catch {
    return null
  }
}

export function writeString(storage: Storage, key: string, value: string): void {
  try {
    if (value === "") storage.removeItem(key)
    else storage.setItem(key, value)
  } catch {
    // See writeJson.
  }
}
