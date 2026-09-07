import { useEffect, useState } from "react"
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription } from "@/components/ui/dialog"
import { StartupApi } from "@/api/endpoints"
import type { Startup } from "@/types"
import { LoadingState } from "@/components/ui/state-views"
import { Badge } from "@/components/ui/badge"

export function StartupProfileDialog({
  startupId, open, onOpenChange,
}: { startupId: string | null; open: boolean; onOpenChange: (open: boolean) => void }) {
  const [startup, setStartup] = useState<Startup | null>(null)

  useEffect(() => {
    if (open && startupId) {
      setStartup(null)
      StartupApi.get(startupId).then(setStartup).catch(() => setStartup(null))
    }
  }, [open, startupId])

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-xl">
        {!startup && <LoadingState label="Loading startup profile…" />}
        {startup && (
          <>
            <DialogHeader>
              <DialogTitle>{startup.companyName}</DialogTitle>
              <DialogDescription>
                {[startup.city, startup.state].filter(Boolean).join(", ")}
                {startup.foundedYear && ` · Founded ${startup.foundedYear}`}
                {startup.teamSize && ` · ${startup.teamSize} team members`}
              </DialogDescription>
            </DialogHeader>
            <div className="space-y-4">
              {startup.description && <p className="text-sm text-slate-600">{startup.description}</p>}

              <div>
                <p className="mb-1.5 text-xs font-semibold uppercase tracking-wide text-slate-400">
                  Pilot readiness
                </p>
                <div className="flex items-center gap-2">
                  <div className="h-2 flex-1 overflow-hidden rounded-full bg-slate-100">
                    <div className="h-full rounded-full bg-brand-600" style={{ width: `${startup.readinessScore}%` }} />
                  </div>
                  <span className="text-sm font-medium text-slate-700">{startup.readinessScore}/100</span>
                </div>
              </div>

              <div>
                <p className="mb-1.5 text-xs font-semibold uppercase tracking-wide text-slate-400">Capabilities</p>
                <div className="flex flex-wrap gap-1.5">
                  {startup.capabilities.map((c) => (
                    <Badge key={c.id} variant="brand">
                      {c.technologyTag} · {c.domainTag} (L{c.proficiencyLevel})
                    </Badge>
                  ))}
                  {startup.capabilities.length === 0 && <p className="text-sm text-slate-400">None listed yet.</p>}
                </div>
              </div>

              <div>
                <p className="mb-1.5 text-xs font-semibold uppercase tracking-wide text-slate-400">Past projects</p>
                <div className="space-y-2">
                  {startup.projects.map((p) => (
                    <div key={p.id} className="rounded-lg border border-slate-200 p-3 text-sm">
                      <div className="mb-0.5 flex items-center justify-between gap-2">
                        <p className="font-medium text-slate-800">{p.title}</p>
                        <Badge variant={p.clientType === "GOVERNMENT" ? "success" : "outline"}>
                          {p.clientType === "GOVERNMENT" ? "Govt client" : "Private client"}
                        </Badge>
                      </div>
                      <p className="text-xs text-slate-500">{p.domain} {p.year && `· ${p.year}`} {p.technologyStack && `· ${p.technologyStack}`}</p>
                      {p.outcomeSummary && <p className="mt-1 text-xs text-slate-600">{p.outcomeSummary}</p>}
                    </div>
                  ))}
                  {startup.projects.length === 0 && <p className="text-sm text-slate-400">None listed yet.</p>}
                </div>
              </div>
            </div>
          </>
        )}
      </DialogContent>
    </Dialog>
  )
}
