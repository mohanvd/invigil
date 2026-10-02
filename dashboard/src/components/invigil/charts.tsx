import { Bar, BarChart, CartesianGrid, Line, LineChart, ReferenceArea, Scatter, ScatterChart, XAxis, YAxis } from "recharts"

import { ChartContainer, ChartTooltip } from "@/components/ui/chart"
import type { ChartConfig } from "@/components/ui/chart"
import type { SpectrumMessage } from "@/data/contract"
import { BANDS, BAND_EDGES_M } from "@/data/types"
import type { Band, RssiByDistancePoint, RssiReading } from "@/data/types"
import { formatClock } from "@/lib/format"

import { BAND_STYLE, DEVICE_LABEL } from "./bands"

// Gridlines are line, axes are line-strong, tick labels are ink-muted in mono.
const AXIS = { stroke: "var(--input)" }
const TICK = { fontFamily: "var(--font-mono)", fontSize: 11, fill: "var(--muted-foreground)" }
const GRID = "var(--border)"

function TooltipBox({ rows }: { rows: [string, string][] }) {
  return (
    <div className="grid grid-cols-[auto_auto] gap-x-3 gap-y-0.5 rounded-md border bg-popover px-2.5 py-1.5 text-[13px] text-popover-foreground">
      {rows.map(([label, value]) => (
        <div key={label} className="contents">
          <span className="text-muted-foreground">{label}</span>
          <span className="data text-right">{value}</span>
        </div>
      ))}
    </div>
  )
}

/** A tick every 30 s, on the half minute, so the labels do not slide as time passes. */
function timeTicks(from: number, to: number): number[] {
  const step = 30_000
  const ticks: number[] = []
  for (let t = Math.ceil(from / step) * step; t <= to; t += step) ticks.push(t)
  return ticks
}

const rssiConfig = { rssi: { label: "RSSI", color: "var(--chart-4)" } } satisfies ChartConfig

/** RSSI over time for one device. The line is not a band, so it is drawn in ink. */
export function RssiTimeChart({ readings, from, to }: { readings: RssiReading[]; from: number; to: number }) {
  return (
    <ChartContainer config={rssiConfig} className="aspect-auto h-56 w-full">
      <LineChart data={readings} margin={{ top: 8, right: 28, bottom: 0, left: 0 }} accessibilityLayer>
        <CartesianGrid stroke={GRID} vertical={false} />
        <XAxis
          dataKey="ts"
          type="number"
          domain={[from, to]}
          allowDataOverflow
          ticks={timeTicks(from, to)}
          tickFormatter={(ts: number) => formatClock(ts)}
          tick={TICK}
          axisLine={AXIS}
          tickLine={AXIS}
          tickMargin={6}
        />
        <YAxis
          dataKey="rssi"
          type="number"
          domain={[-100, -30]}
          ticks={[-100, -90, -80, -70, -60, -50, -40, -30]}
          tick={TICK}
          axisLine={AXIS}
          tickLine={false}
          width={44}
          tickFormatter={(v: number) => `${v}`}
        />
        <ChartTooltip
          cursor={{ stroke: "var(--input)" }}
          isAnimationActive={false}
          content={({ active, payload }) => {
            const point = payload?.[0]?.payload as RssiReading | undefined
            if (!active || !point) return null
            return (
              <TooltipBox
                rows={[
                  ["Time", formatClock(point.ts)],
                  ["RSSI", `${point.rssi} dBm`],
                ]}
              />
            )
          }}
        />
        <Line dataKey="rssi" type="linear" stroke="var(--color-rssi)" strokeWidth={1.5} dot={false} isAnimationActive={false} />
      </LineChart>
    </ChartContainer>
  )
}

const distanceConfig = {
  near: { label: "Near", color: "var(--near)" },
  mid: { label: "Mid", color: "var(--mid)" },
  far: { label: "Far", color: "var(--far)" },
} satisfies ChartConfig

const BAND_FROM_M: Record<Band, number> = { near: 0, mid: BAND_EDGES_M.near, far: BAND_EDGES_M.mid }

/** Median RSSI of each session against its distance, with the three bands shaded behind. */
export function RssiDistanceChart({ points }: { points: RssiByDistancePoint[] }) {
  return (
    <ChartContainer config={distanceConfig} className="aspect-auto h-72 w-full">
      <ScatterChart margin={{ top: 8, right: 12, bottom: 16, left: 8 }} accessibilityLayer>
        {BANDS.map((band) => (
          <ReferenceArea
            key={band}
            x1={BAND_FROM_M[band]}
            x2={BAND_EDGES_M[band]}
            fill={BAND_STYLE[band].softVar}
            fillOpacity={1}
            stroke="none"
            label={{
              value: band.toUpperCase(),
              position: "insideTop",
              offset: 8,
              style: { ...TICK, fill: "var(--foreground)", fontWeight: 500, letterSpacing: "0.08em" },
            }}
          />
        ))}
        <CartesianGrid stroke={GRID} vertical={false} />
        <XAxis
          dataKey="distanceM"
          type="number"
          domain={[0, BAND_EDGES_M.far]}
          ticks={[0, 0.5, 1, 1.5, 2, 2.5, 3, 3.5]}
          tick={TICK}
          axisLine={AXIS}
          tickLine={AXIS}
          tickMargin={6}
          label={{ value: "Distance from the unit, m", position: "insideBottom", offset: -10, style: TICK }}
        />
        <YAxis
          dataKey="rssi"
          type="number"
          domain={[-90, -40]}
          ticks={[-90, -80, -70, -60, -50, -40]}
          tick={TICK}
          axisLine={AXIS}
          tickLine={false}
          width={56}
          label={{ value: "Median RSSI, dBm", angle: -90, position: "insideLeft", offset: 14, style: { ...TICK, textAnchor: "middle" } }}
        />
        <ChartTooltip
          cursor={false}
          isAnimationActive={false}
          content={({ active, payload }) => {
            const point = payload?.[0]?.payload as RssiByDistancePoint | undefined
            if (!active || !point) return null
            return (
              <TooltipBox
                rows={[
                  ["Session", point.session],
                  ["Device type", DEVICE_LABEL[point.type]],
                  ["Distance", `${point.distanceM} m`],
                  ["Median RSSI", `${point.rssi} dBm`],
                ]}
              />
            )
          }}
        />
        {BANDS.map((band) => (
          <Scatter
            key={band}
            name={band}
            data={points.filter((p) => p.band === band)}
            fill={`var(--color-${band})`}
            isAnimationActive={false}
          />
        ))}
      </ScatterChart>
    </ChartContainer>
  )
}

const spectrumConfig = { hits: { label: "Hits", color: "var(--chart-4)" } } satisfies ChartConfig

/** RPD hits per nRF24L01 channel for the latest scan window. Channel c is 2400 + c MHz. */
export function SpectrumChart({ spectrum }: { spectrum: SpectrumMessage }) {
  const data = spectrum.hits.map((hits, channel) => ({ channel, hits }))
  return (
    <ChartContainer config={spectrumConfig} className="aspect-auto h-44 w-full">
      <BarChart data={data} margin={{ top: 8, right: 12, bottom: 16, left: 0 }} barCategoryGap={1} accessibilityLayer>
        <CartesianGrid stroke={GRID} vertical={false} />
        <XAxis
          dataKey="channel"
          type="number"
          domain={[-0.5, 125.5]}
          ticks={[0, 25, 50, 75, 100, 125]}
          tick={TICK}
          axisLine={AXIS}
          tickLine={AXIS}
          tickMargin={6}
          label={{ value: "Channel (2400 MHz + channel)", position: "insideBottom", offset: -10, style: TICK }}
        />
        <YAxis
          type="number"
          domain={[0, spectrum.sweeps]}
          allowDecimals={false}
          tick={TICK}
          axisLine={AXIS}
          tickLine={false}
          width={44}
        />
        <ChartTooltip
          cursor={{ fill: "var(--muted)" }}
          isAnimationActive={false}
          content={({ active, payload }) => {
            const point = payload?.[0]?.payload as { channel: number; hits: number } | undefined
            if (!active || !point) return null
            return (
              <TooltipBox
                rows={[
                  ["Channel", `${point.channel} (${2400 + point.channel} MHz)`],
                  ["Hits", `${point.hits} of ${spectrum.sweeps} sweeps`],
                ]}
              />
            )
          }}
        />
        <Bar dataKey="hits" fill="var(--color-hits)" isAnimationActive={false} />
      </BarChart>
    </ChartContainer>
  )
}
