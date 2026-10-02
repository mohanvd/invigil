import {
  FlexRender,
  createColumnHelper,
  createSortedRowModel,
  rowSortingFeature,
  tableFeatures,
  useTable,
} from "@tanstack/react-table"
import type { SortingState } from "@tanstack/react-table"
import { ArrowDownIcon, ArrowUpIcon, ChevronsUpDownIcon, FolderOpenIcon, SearchIcon, SearchXIcon } from "lucide-react"
import { useCallback, useMemo, useState } from "react"

import { useData, useSourceQuery } from "@/app/data"
import { EmptyState } from "@/components/invigil/empty-state"
import { Page, Panel } from "@/components/page"
import { Input } from "@/components/ui/input"
import { Skeleton } from "@/components/ui/skeleton"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import type { DataSource, SessionSummary } from "@/data/types"
import { formatDateTime, formatDuration } from "@/lib/format"
import { cn } from "@/lib/utils"

const features = tableFeatures({
  rowSortingFeature,
  sortedRowModel: createSortedRowModel(),
})

const columnHelper = createColumnHelper<typeof features, SessionSummary>()

const columns = columnHelper.columns([
  columnHelper.accessor("name", {
    header: "Name",
    cell: (info) => <span className="data text-[13px]">{info.getValue()}</span>,
  }),
  columnHelper.accessor("startedAt", {
    header: "Date",
    cell: (info) => <span className="data text-[13px]">{formatDateTime(info.getValue())}</span>,
  }),
  columnHelper.accessor("durationS", {
    header: "Duration",
    meta: { align: "right" },
    cell: (info) => <span className="data text-[13px]">{formatDuration(info.getValue())}</span>,
  }),
  columnHelper.accessor("devices", {
    header: "Devices",
    meta: { align: "right" },
    cell: (info) => <span className="data text-[13px]">{info.getValue()}</span>,
  }),
  columnHelper.accessor("labelled", {
    header: "Label",
    cell: (info) =>
      info.getValue() ? (
        <span className="inline-flex h-5 items-center rounded-sm bg-clear-soft px-1.5 label-caps">Labelled</span>
      ) : (
        <span className="inline-flex h-5 items-center rounded-sm border border-dashed border-line-strong px-1.5 label-caps text-muted-foreground">
          Not labelled
        </span>
      ),
  }),
])

function isRight(meta: unknown): boolean {
  return typeof meta === "object" && meta !== null && (meta as { align?: string }).align === "right"
}

function SessionsTable({ sessions }: { sessions: SessionSummary[] }) {
  const [sorting, setSorting] = useState<SortingState>([{ id: "startedAt", desc: true }])
  const table = useTable({
    features,
    data: sessions,
    columns,
    state: { sorting },
    onSortingChange: setSorting,
    getRowId: (row) => row.name,
  })

  return (
    <Table>
      <TableHeader>
        {table.getHeaderGroups().map((group) => (
          <TableRow key={group.id} className="hover:bg-transparent">
            {group.headers.map((header) => {
              const sorted = header.column.getIsSorted()
              const right = isRight(header.column.columnDef.meta)
              return (
                <TableHead
                  key={header.id}
                  className={cn("h-9 px-4", right && "text-right")}
                  aria-sort={sorted === "asc" ? "ascending" : sorted === "desc" ? "descending" : "none"}
                >
                  <button
                    type="button"
                    onClick={header.column.getToggleSortingHandler()}
                    className={cn(
                      "inline-flex cursor-pointer items-center gap-1 rounded-sm label-caps text-muted-foreground hover:text-foreground",
                      sorted && "text-foreground"
                    )}
                  >
                    <FlexRender header={header} />
                    {sorted === "asc" ? (
                      <ArrowUpIcon className="size-3" aria-hidden="true" />
                    ) : sorted === "desc" ? (
                      <ArrowDownIcon className="size-3" aria-hidden="true" />
                    ) : (
                      <ChevronsUpDownIcon className="size-3 opacity-60" aria-hidden="true" />
                    )}
                  </button>
                </TableHead>
              )
            })}
          </TableRow>
        ))}
      </TableHeader>
      <TableBody>
        {table.getRowModel().rows.map((row) => (
          <TableRow key={row.id}>
            {row.getAllCells().map((cell) => (
              <TableCell key={cell.id} className={cn("px-4 py-2", isRight(cell.column.columnDef.meta) && "text-right")}>
                <FlexRender cell={cell} />
              </TableCell>
            ))}
          </TableRow>
        ))}
      </TableBody>
    </Table>
  )
}

function LoadingRows() {
  return (
    <div className="flex flex-col gap-2 p-4" aria-label="Loading sessions">
      {[0, 1, 2, 3, 4, 5, 6, 7].map((i) => (
        <Skeleton key={i} className="h-7" />
      ))}
    </div>
  )
}

export function SessionsPage() {
  const { source } = useData()
  const load = useCallback((s: DataSource) => s.listSessions(), [])
  const query = useSourceQuery(load)
  const [search, setSearch] = useState("")

  const sessions = query.status === "ready" ? query.value : null
  const matching = useMemo(() => {
    const needle = search.trim().toLowerCase()
    if (!sessions) return []
    return needle === "" ? sessions : sessions.filter((s) => s.name.toLowerCase().includes(needle))
  }, [sessions, search])

  return (
    <Page
      title="Sessions"
      description="Recordings made with the logger. One session is one device, one distance, one state, for three minutes."
    >
      <Panel
        className="col-span-12"
        title="Recorded sessions"
        description={
          sessions && sessions.length > 0
            ? `${matching.length} of ${sessions.length} shown, ${sessions.filter((s) => s.labelled).length} labelled.`
            : undefined
        }
        flush
        actions={
          <div className="relative">
            <SearchIcon className="pointer-events-none absolute top-1/2 left-2 size-3.5 -translate-y-1/2 text-muted-foreground" />
            <Input
              type="search"
              value={search}
              onChange={(event) => setSearch(event.target.value)}
              placeholder="Search by name"
              aria-label="Search sessions by name"
              className="h-7 w-56 pl-7 text-[13px]"
              disabled={!sessions || sessions.length === 0}
            />
          </div>
        }
      >
        {query.status === "loading" ? (
          <LoadingRows />
        ) : sessions === null ? (
          <EmptyState icon={<FolderOpenIcon />} title="Sessions cannot be listed yet">
            Recorded sessions will be listed here with their date, duration, devices and label. The logger writes them to
            data/raw/ on the laptop, and nothing serves that folder to the browser yet. {source.kind === "live" ? "Switch to Demo in Settings to see the table." : ""}
          </EmptyState>
        ) : sessions.length === 0 ? (
          <EmptyState icon={<FolderOpenIcon />} title="No sessions recorded">
            Each recording made with the logger appears here. None has been recorded yet.
          </EmptyState>
        ) : matching.length === 0 ? (
          <EmptyState icon={<SearchXIcon />} title="No session matches">
            No session name contains "{search.trim()}". Names follow type-band-state-repeat, for example
            earpiece-near-streaming-1.
          </EmptyState>
        ) : (
          <SessionsTable sessions={matching} />
        )}
      </Panel>
    </Page>
  )
}
