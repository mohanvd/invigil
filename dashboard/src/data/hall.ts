import type { Band } from "./types"

// The 6-seat mini hall, seen from above, in metres. The unit sits in the
// middle of the front wall at (0, 0); x runs along the wall, y into the room.
//
// PLACEHOLDER: the hall size and the seat positions are a drawing guess, not a
// survey. Measure the real hall with a tape and replace these numbers.
export const HALL = {
  widthM: 4.4,
  depthM: 3.8,
  seats: [
    { id: "S1", x: -1.3, y: 1.25 },
    { id: "S2", x: 0, y: 1.25 },
    { id: "S3", x: 1.3, y: 1.25 },
    { id: "S4", x: -1.3, y: 2.55 },
    { id: "S5", x: 0, y: 2.55 },
    { id: "S6", x: 1.3, y: 2.55 },
  ],
} as const

/** Where a band's devices are drawn: the middle of the band, in metres from the unit. */
export const BAND_DRAW_RADIUS_M: Record<Band, number> = { near: 0.62, mid: 1.5, far: 2.8 }
