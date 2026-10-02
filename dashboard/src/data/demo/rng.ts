export interface Rng {
  /** Uniform in [0, 1). */
  next(): number
  uniform(lo: number, hi: number): number
  gauss(mean: number, sd: number): number
  hex(chars: number): string
}

/** mulberry32: small, fast, and the same sequence on every machine for a given seed. */
export function createRng(seed: number): Rng {
  let a = seed >>> 0

  function next(): number {
    a = (a + 0x6d2b79f5) >>> 0
    let t = a
    t = Math.imul(t ^ (t >>> 15), t | 1)
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61)
    return ((t ^ (t >>> 14)) >>> 0) / 4_294_967_296
  }

  return {
    next,
    uniform(lo, hi) {
      return lo + (hi - lo) * next()
    },
    gauss(mean, sd) {
      // Box-Muller. 1 - next() keeps the log away from zero.
      const u = 1 - next()
      const v = next()
      return mean + sd * Math.sqrt(-2 * Math.log(u)) * Math.cos(2 * Math.PI * v)
    },
    hex(chars) {
      let out = ""
      for (let i = 0; i < chars; i++) out += Math.floor(next() * 16).toString(16)
      return out
    },
  }
}
