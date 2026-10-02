import { ChartScatterIcon, Grid3x3Icon } from "lucide-react"
import { useCallback } from "react"

import { useSourceQuery } from "@/app/data"
import { RssiDistanceChart } from "@/components/invigil/charts"
import { ConfusionMatrix } from "@/components/invigil/confusion-matrix"
import { EmptyState } from "@/components/invigil/empty-state"
import { Metric } from "@/components/invigil/metric"
import { Page, Panel } from "@/components/page"
import { Skeleton } from "@/components/ui/skeleton"
import { REQUIREMENTS, requirementStatus } from "@/data/requirements"
import type { DataSource } from "@/data/types"
import { formatDateTime } from "@/lib/format"

const NO_RUN = "No test run has been recorded. Run python -m ml.train on labelled sessions; its report is not served to the browser yet."

export function ResultsPage() {
  const load = useCallback((s: DataSource) => s.loadResults(), [])
  const query = useSourceQuery(load)
  const loading = query.status === "loading"
  const report = query.status === "ready" ? query.value : null

  return (
    <Page
      title="Results"
      description={
        report
          ? `Test run ${report.name}, ${formatDateTime(report.generatedAt)}. Measured on held-out sessions, against the six design requirements.`
          : "The six design requirements, each with its target and the value measured on held-out sessions."
      }
    >
      {REQUIREMENTS.map((requirement) => {
        if (loading) {
          return <Skeleton key={requirement.id} className="col-span-12 h-[150px] rounded-lg sm:col-span-6 xl:col-span-4" />
        }
        const result = report?.requirements.find((r) => r.id === requirement.id)
        const value = result?.value ?? null
        return (
          <Metric
            key={requirement.id}
            className="col-span-12 sm:col-span-6 xl:col-span-4"
            size="lg"
            label={`${requirement.id}. ${requirement.title}`}
            value={value === null ? null : value.toFixed(requirement.decimals)}
            unit={requirement.unit}
            target={requirement.target}
            status={requirementStatus(requirement, value)}
            hint={result?.note ?? "Not measured yet."}
          />
        )
      })}

      <Panel
        className="col-span-12 xl:col-span-7"
        title="Device type confusion matrix"
        description="Rows are the true type, columns the predicted type."
      >
        {loading ? (
          <Skeleton className="h-56" />
        ) : report ? (
          <ConfusionMatrix
            matrix={report.typeMatrix}
            caption="Figure (1) Device type, counted in 5 s windows from held-out sessions."
          />
        ) : (
          <EmptyState icon={<Grid3x3Icon />} title="No confusion matrix yet">
            The counts of true against predicted device type appear here. {NO_RUN}
          </EmptyState>
        )}
      </Panel>

      <Panel
        className="col-span-12 xl:col-span-5"
        title="Distance band confusion matrix"
        description="Rows are the true band, columns the predicted band."
      >
        {loading ? (
          <Skeleton className="h-56" />
        ) : report ? (
          <ConfusionMatrix
            matrix={report.bandMatrix}
            caption="Figure (2) Distance band, counted in 5 s windows from held-out sessions."
          />
        ) : (
          <EmptyState icon={<Grid3x3Icon />} title="No confusion matrix yet">
            The counts of true against predicted distance band appear here. {NO_RUN}
          </EmptyState>
        )}
      </Panel>

      <Panel
        className="col-span-12"
        title="RSSI by distance"
        description="One dot per labelled session: its median RSSI at the distance it was recorded."
      >
        {loading ? (
          <Skeleton className="h-72" />
        ) : report && report.rssiByDistance.length > 0 ? (
          <figure className="flex flex-col gap-3">
            <RssiDistanceChart points={report.rssiByDistance} />
            <figcaption className="text-[13px] text-muted-foreground">
              Figure (3) Median RSSI against distance from the unit. The shaded bands are near, mid and far.
            </figcaption>
          </figure>
        ) : (
          <EmptyState icon={<ChartScatterIcon />} title="No calibration data yet">
            Each labelled session adds one dot: its median RSSI at its measured distance, over the near, mid and far
            bands. {NO_RUN}
          </EmptyState>
        )}
      </Panel>
    </Page>
  )
}
