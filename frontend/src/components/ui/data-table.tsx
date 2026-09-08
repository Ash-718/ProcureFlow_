import type { ReactNode } from "react"
import { cn } from "@/lib/utils"

export interface Column<T> {
  /** Column heading. */
  header: string
  /** Cell renderer. Given the row, returns whatever should be displayed. */
  cell: (row: T) => ReactNode
  /** Extra classes for the cell — mainly `text-right`/`tabular-nums`. */
  className?: string
  /** Hide below `md`. Use for secondary columns so mobile stays readable. */
  hideOnMobile?: boolean
}

/**
 * A plain, scannable table.
 *
 * Tables are for comparison, so this one keeps the visual noise low: no zebra
 * striping, no inner vertical rules, one hairline between rows. The header is
 * sticky because the audit log runs to a hundred rows.
 *
 * Responsiveness is handled two ways rather than by shrinking: secondary
 * columns opt out below `md` via `hideOnMobile`, and the whole table scrolls
 * horizontally inside its own container so the page itself never does.
 */
export function DataTable<T>({
  columns,
  rows,
  keyOf,
  onRowClick,
  empty,
  caption,
  className,
}: {
  columns: Column<T>[]
  rows: T[]
  keyOf: (row: T) => string
  onRowClick?: (row: T) => void
  /** Shown in place of the body when there are no rows. */
  empty?: ReactNode
  /** Screen-reader description of what the table contains. */
  caption?: string
  className?: string
}) {
  if (rows.length === 0 && empty) {
    return <>{empty}</>
  }

  return (
    <div
      className={cn(
        "overflow-x-auto rounded-lg border border-slate-200 bg-white",
        className,
      )}
    >
      <table className="w-full border-collapse text-sm">
        {caption && <caption className="sr-only">{caption}</caption>}
        <thead className="sticky top-0 z-10 bg-slate-50">
          <tr className="border-b border-slate-200">
            {columns.map((column) => (
              <th
                key={column.header}
                scope="col"
                className={cn(
                  "whitespace-nowrap px-4 py-2.5 text-left text-xs font-semibold uppercase tracking-wide text-slate-600",
                  column.hideOnMobile && "hidden md:table-cell",
                  column.className,
                )}
              >
                {column.header}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr
              key={keyOf(row)}
              onClick={onRowClick ? () => onRowClick(row) : undefined}
              // A clickable row is reachable and activatable from the keyboard;
              // a decorative one stays out of the tab order entirely.
              tabIndex={onRowClick ? 0 : undefined}
              onKeyDown={
                onRowClick
                  ? (event) => {
                      if (event.key === "Enter" || event.key === " ") {
                        event.preventDefault()
                        onRowClick(row)
                      }
                    }
                  : undefined
              }
              className={cn(
                "border-b border-slate-100 last:border-0",
                onRowClick &&
                  "cursor-pointer transition-colors hover:bg-slate-50 focus-visible:bg-brand-50 focus-visible:outline-none",
              )}
            >
              {columns.map((column) => (
                <td
                  key={column.header}
                  className={cn(
                    "px-4 py-2.5 align-middle text-slate-700",
                    column.hideOnMobile && "hidden md:table-cell",
                    column.className,
                  )}
                >
                  {column.cell(row)}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

/** Row-shaped placeholder, so a loading table keeps the page height stable. */
export function TableSkeleton({ rows = 5, columns = 4 }: { rows?: number; columns?: number }) {
  return (
    <div className="overflow-hidden rounded-lg border border-slate-200 bg-white">
      <div className="border-b border-slate-200 bg-slate-50 px-4 py-2.5">
        <div className="h-3 w-32 animate-pulse rounded bg-slate-200" />
      </div>
      {Array.from({ length: rows }).map((_, rowIndex) => (
        <div
          key={rowIndex}
          className="flex gap-4 border-b border-slate-100 px-4 py-3 last:border-0"
        >
          {Array.from({ length: columns }).map((_, cellIndex) => (
            <div
              key={cellIndex}
              className="h-3 flex-1 animate-pulse rounded bg-slate-100"
            />
          ))}
        </div>
      ))}
    </div>
  )
}
