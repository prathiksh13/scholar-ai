import { AlertTriangle, CheckCircle2, Gauge } from 'lucide-react'

function issueTone(severity = 'info') {
  if (severity === 'error') return 'text-rose-200 bg-rose-500/10 border-rose-500/15'
  if (severity === 'warning') return 'text-amber-100 bg-amber-500/10 border-amber-500/15'
  return 'text-cyan-100 bg-cyan-500/10 border-cyan-500/15'
}

export default function CompliancePanel({ report, format = 'IEEE', compact = false }) {
  const score = report?.score ?? 0
  const issues = report?.issues || []
  const gauge = Math.max(0, Math.min(100, score))

  return (
    <div className={`compliance-panel ${compact ? 'is-compact' : ''}`}>
      <div className="flex items-start justify-between gap-4">
        <div>
          <p className="text-xs uppercase tracking-[0.3em] text-cyan-300/70">Compliance</p>
          <h3 className="mt-2 text-lg font-semibold text-white">{format} compliance</h3>
          <p className="mt-1 text-sm text-slate-400">
            Live score and issues for the current semantic snapshot.
          </p>
        </div>
        <div className="score-ring" style={{ '--score': gauge }}>
          <span>{report ? `${gauge}%` : '...'}</span>
        </div>
      </div>

      {!compact && (
        <>
          <div className="mt-4 flex items-center gap-2 text-xs text-slate-500">
            <Gauge className="h-4 w-4 text-cyan-300" />
            {report ? `IEEE compliance score: ${gauge}%` : 'Awaiting formatted compliance output...'}
          </div>

          {issues.length > 0 ? (
            <div className="mt-4 space-y-2">
              {issues.map((issue) => (
                <div key={issue.id} className={`rounded-2xl border px-3 py-2 text-sm ${issueTone(issue.severity)}`}>
                  <div className="flex items-start gap-2">
                    {issue.severity === 'error' ? (
                      <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" />
                    ) : (
                      <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0" />
                    )}
                    <div>
                      <p className="font-medium">{issue.message}</p>
                      {issue.explanation && <p className="mt-1 text-xs opacity-80">{issue.explanation}</p>}
                    </div>
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <div className="mt-4 rounded-2xl border border-dashed border-white/10 bg-white/5 px-3 py-4 text-sm text-slate-500">
              No compliance issues detected yet.
            </div>
          )}
        </>
      )}
    </div>
  )
}