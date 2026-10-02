import { useId } from "react"
import type { KeyboardEvent } from "react"

import { BAND_DRAW_RADIUS_M, HALL } from "@/data/hall"
import type { MapDevice } from "@/data/selectors"
import { BANDS, BAND_EDGES_M } from "@/data/types"
import type { Band } from "@/data/types"

import { BAND_RANGE, BAND_STYLE, DEVICE_LABEL } from "./bands"
import { DeviceIcon } from "./icons"

const PX_PER_M = 100
const PAD = 14
const WALL = 4
const W = HALL.widthM * PX_PER_M
const H = HALL.depthM * PX_PER_M
const CX = PAD + W / 2
const TOP = PAD

// Devices are spread along their band's arc. The angle is measured from the
// front wall, so 90 degrees points straight into the room.
const ARC_FROM_DEG = 28
const ARC_TO_DEG = 152

// Where each zone's label sits, in metres from the unit, clear of the seats.
const LABEL_AT: Record<Band, { x: number; y: number }> = {
  near: { x: -0.52, y: 0.3 },
  mid: { x: -1.45, y: 0.4 },
  far: { x: 0, y: 3.2 },
}

function arcPoint(radiusM: number, angleDeg: number): { x: number; y: number } {
  const a = (angleDeg * Math.PI) / 180
  return { x: CX + Math.cos(a) * radiusM * PX_PER_M, y: TOP + Math.sin(a) * radiusM * PX_PER_M }
}

function placeDevices(devices: MapDevice[]) {
  return BANDS.flatMap((band) => {
    const inBand = devices.filter((d) => d.band === band)
    return inBand.map((device, i) => {
      const t = (i + 1) / (inBand.length + 1)
      // Start from the right so the zone labels on the left stay readable.
      const angle = ARC_FROM_DEG + (ARC_TO_DEG - ARC_FROM_DEG) * t * 0.82
      return { device, ...arcPoint(BAND_DRAW_RADIUS_M[band], angle) }
    })
  })
}

interface HallMapProps {
  devices: MapDevice[]
  selectedKey: string | null
  onSelect(device: MapDevice): void
}

/**
 * The hall from above: the unit on the front wall, the three distance bands
 * as soft tints, the six seats, and each detected device in its band.
 */
export function HallMap({ devices, selectedKey, onSelect }: HallMapProps) {
  const clipId = useId()
  const placed = placeDevices(devices)
  const zones: Band[] = ["far", "mid", "near"]

  return (
    <svg
      xmlns="http://www.w3.org/2000/svg"
      viewBox={`0 0 ${W + PAD * 2} ${H + PAD * 2}`}
      className="block h-auto w-full"
      role="group"
      aria-label={`Hall map. ${devices.length} ${devices.length === 1 ? "device" : "devices"} placed.`}
    >
      <defs>
        <clipPath id={clipId}>
          <rect x={PAD} y={TOP} width={W} height={H} />
        </clipPath>
      </defs>

      <rect x={PAD} y={TOP} width={W} height={H} fill="var(--paper-sunken)" />

      <g clipPath={`url(#${clipId})`}>
        {zones.map((band) => (
          <circle key={band} cx={CX} cy={TOP} r={BAND_EDGES_M[band] * PX_PER_M} fill={BAND_STYLE[band].softVar} />
        ))}
        {zones.map((band) => (
          <circle
            key={band}
            cx={CX}
            cy={TOP}
            r={BAND_EDGES_M[band] * PX_PER_M}
            fill="none"
            stroke={BAND_STYLE[band].stroke}
            strokeWidth="1"
            strokeDasharray="2 5"
          />
        ))}
      </g>

      {BANDS.map((band) => {
        const p = LABEL_AT[band]
        const x = CX + p.x * PX_PER_M
        const y = TOP + p.y * PX_PER_M
        return (
          <text key={band} x={x} y={y} textAnchor="middle" className="fill-foreground font-mono text-[11px] font-medium tracking-[0.08em] uppercase">
            {band}
            <tspan x={x} dy="13" className="fill-muted-foreground tracking-normal normal-case">
              {BAND_RANGE[band]}
            </tspan>
          </text>
        )
      })}

      {HALL.seats.map((seat) => {
        const x = CX + seat.x * PX_PER_M
        const y = TOP + seat.y * PX_PER_M
        return (
          <g key={seat.id}>
            <rect x={x - 26} y={y - 17} width="52" height="34" rx="2" fill="none" stroke="var(--input)" strokeDasharray="3 3" />
            <text x={x - 21} y={y - 7} className="fill-muted-foreground font-mono text-[10px]">
              {seat.id}
            </text>
          </g>
        )
      })}

      {/* The walls, and the unit on the front wall, as in the logo. */}
      <rect x={PAD} y={TOP} width={W} height={H} fill="none" stroke="var(--input)" strokeWidth={WALL} />
      <circle cx={CX} cy={TOP} r="9" fill="var(--foreground)" />
      <text x={CX + 16} y={TOP + 20} className="fill-foreground font-mono text-[11px] font-medium tracking-[0.08em]">
        UNIT
      </text>

      {placed.map(({ device, x, y }) => {
        const selected = device.key === selectedKey
        const name = device.label ?? DEVICE_LABEL[device.type]
        const select = () => onSelect(device)
        const onKeyDown = (event: KeyboardEvent) => {
          if (event.key === "Enter" || event.key === " ") {
            event.preventDefault()
            select()
          }
        }
        return (
          <g
            key={device.key}
            role="button"
            tabIndex={0}
            aria-pressed={selected}
            aria-label={`${name}, ${device.band} band`}
            onClick={select}
            onKeyDown={onKeyDown}
            className="cursor-pointer"
          >
            <title>{`${name}, ${device.band} band`}</title>
            <circle
              cx={x}
              cy={y}
              r="15"
              fill="var(--card)"
              stroke={BAND_STYLE[device.band].stroke}
              strokeWidth={selected ? 4 : 2}
            />
            <DeviceIcon
              type={device.type}
              x={x - 9}
              y={y - 9}
              width="18"
              height="18"
              className={device.type === "allowed" ? "text-clear" : "text-foreground"}
            />
          </g>
        )
      })}
    </svg>
  )
}
