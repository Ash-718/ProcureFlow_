import type { ReactNode } from "react"
import { Link } from "react-router-dom"
import { ChevronRight } from "lucide-react"
import { cn } from "@/lib/utils"

export interface Crumb {
  label: string
  to?: string
}

/**
 * The standard heading block for a page.
 *
 * Every page used to hand-roll its own title/description/actions row, which
 * drifted: different sizes, different spacing, actions sometimes above and
 * sometimes below. One component keeps the top of every screen identical, and
 * gives breadcrumbs a consistent home for the deep detail routes.
 */
export function PageHeader({
  title,
  description,
  breadcrumbs,
  actions,
  meta,
  className,
}: {
  title: string
  description?: string
  breadcrumbs?: Crumb[]
  actions?: ReactNode
  /** Small status chips or counts shown beside the title. */
  meta?: ReactNode
  className?: string
}) {
  return (
    <div className={cn("space-y-3", className)}>
      {breadcrumbs && breadcrumbs.length > 0 && (
        <nav aria-label="Breadcrumb">
          <ol className="flex flex-wrap items-center gap-1 text-xs text-slate-500">
            {breadcrumbs.map((crumb, index) => (
              <li key={`${crumb.label}-${index}`} className="flex items-center gap-1">
                {index > 0 && <ChevronRight className="h-3 w-3 text-slate-300" aria-hidden />}
                {crumb.to ? (
                  <Link to={crumb.to} className="rounded hover:text-brand-700 hover:underline">
                    {crumb.label}
                  </Link>
                ) : (
                  <span className="text-slate-700">{crumb.label}</span>
                )}
              </li>
            ))}
          </ol>
        </nav>
      )}

      <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <div className="min-w-0 space-y-1">
          <div className="flex flex-wrap items-center gap-2.5">
            <h1 className="text-xl font-semibold tracking-tight text-slate-900 sm:text-2xl">
              {title}
            </h1>
            {meta}
          </div>
          {description && (
            <p className="max-w-2xl text-sm leading-relaxed text-slate-600">{description}</p>
          )}
        </div>
        {actions && <div className="flex shrink-0 flex-wrap items-center gap-2">{actions}</div>}
      </div>
    </div>
  )
}

/**
 * Heading for a block within a page. Deliberately much quieter than
 * `PageHeader` so the visual hierarchy on a dense screen stays readable.
 */
export function SectionHeader({
  title,
  description,
  actions,
  icon: Icon,
  className,
}: {
  title: string
  description?: string
  actions?: ReactNode
  icon?: React.ComponentType<{ className?: string }>
  className?: string
}) {
  return (
    <div className={cn("flex items-start justify-between gap-3", className)}>
      <div className="min-w-0 space-y-0.5">
        <h2 className="flex items-center gap-2 text-sm font-semibold text-slate-900">
          {Icon && <Icon className="h-4 w-4 text-slate-400" />}
          {title}
        </h2>
        {description && <p className="text-xs text-slate-500">{description}</p>}
      </div>
      {actions && <div className="shrink-0">{actions}</div>}
    </div>
  )
}
