import { useMemo, useState } from 'react'
import { Clock3, Loader2, Sparkles } from 'lucide-react'

export default function FormatLogPanel({
  logs = [],
  selectedLogId,
  onSelectLog,
  activeFormat,
  selectedLog,
}) {
  const [showSteps, setShowSteps] = useState(true)
  const [showReason, setShowReason] = useState(true)

  const finishedCount = useMemo(
    () => logs.filter((item) => item.status === 'done').length,
    [logs],
  )

  return (
    <div className="analysis-shell flex h-full flex-col">
      <div className="analysis-header border-b border-white/10 px-4 py-3">
        <div className="flex items-start justify-between gap-3">
          <div>
            <p className="text-[10px] uppercase tracking-[0.3em] text-cyan-300/70">
              Live AI formatting stream
            </p>
            <h2 className="mt-1 text-lg font-semibold text-white">Analysis</h2>
            <p className="mt-1 text-xs text-slate-400">
              Watch the formatter explain each transformation as it happens.
            </p>
          </div>
          <div className="analysis-progress rounded-xl border border-cyan-500/15 bg-cyan-500/10 px-3 py-1.5 text-right">
            <p className="text-[9px] uppercase tracking-[0.25em] text-cyan-200/70">
              {activeFormat}
            </p>
            <p className="mt-0.5 text-xs font-medium text-cyan-100">
              {finishedCount}/{logs.length || 0} steps
            </p>
          </div>
        </div>
      </div>

      <div className="analysis-content flex-1 px-4 py-3">
        <div className="analysis-card rounded-2xl border border-white/10 bg-white/[0.04]">
          <button
            type="button"
            className="analysis-card-toggle flex w-full items-center justify-between px-3 py-2 text-left"
            onClick={() => setShowSteps((value) => !value)}
          >
            <p className="text-[11px] font-semibold uppercase tracking-[0.22em] text-slate-300">Reasoning Steps</p>
            <span className="text-xs text-cyan-300">{showSteps ? 'Hide' : 'Show'}</span>
          </button>
          {showSteps && (
            <div className="analysis-steps space-y-2 p-2">
              {logs.map((log) => {
                const active = log.status === 'running'
                const selected = selectedLogId === log.id
                return (
                  <button
                    type="button"
                    key={log.id}
                    onClick={() => onSelectLog?.(log.id)}
                    className={`log-item ${selected ? 'is-selected' : ''} ${active ? 'is-running' : ''}`}
                  >
                    <div className="flex items-start gap-3">
                      <div className={`mt-0.5 log-dot ${active ? 'is-running' : 'is-done'}`}>
                        {active ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Sparkles className="h-3.5 w-3.5" />}
                      </div>
                      <div className="min-w-0 flex-1 text-left">
                        <div className="flex items-center gap-2 text-[10px] font-semibold uppercase tracking-[0.25em] text-slate-500">
                          <span>{log.id}</span>
                          {active && (
                            <span className="inline-flex items-center gap-1 text-cyan-300">
                              <Clock3 className="h-3 w-3" />
                              running
                            </span>
                          )}
                        </div>
                        <p className="mt-1 text-sm text-white">
                          <span className={active ? 'typing-line' : ''} style={active ? { animationDuration: `${Math.max(1.2, (log.message || '').length * 0.03)}s` } : undefined}>
                            {log.message || ''}
                          </span>
                          {active && <span className="typing-cursor" aria-hidden="true" />}
                        </p>
                        {log.explanation && (
                          <p className="mt-1 text-xs leading-relaxed text-slate-500">{log.explanation}</p>
                        )}
                      </div>
                    </div>
                  </button>
                )
              })}

              {logs.length === 0 && (
                <div className="rounded-xl border border-dashed border-white/10 bg-white/5 p-4 text-sm text-slate-500">
                  Upload a DOCX to see live AI reasoning.
                </div>
              )}
            </div>
          )}
        </div>

        <div className="analysis-card mt-3 rounded-2xl border border-cyan-500/10 bg-cyan-500/[0.06]">
          <button
            type="button"
            className="analysis-card-toggle flex w-full items-center justify-between px-3 py-2 text-left"
            onClick={() => setShowReason((value) => !value)}
          >
            <p className="text-[11px] font-semibold uppercase tracking-[0.22em] text-cyan-200/80">Why This Changed</p>
            <span className="text-xs text-cyan-300">{showReason ? 'Hide' : 'Show'}</span>
          </button>
          {showReason && (
            <div className="px-3 pb-3">
              <p className="text-sm font-medium text-white">
                {selectedLog?.message || 'No live action selected yet.'}
              </p>
              <p className="mt-1 text-sm leading-relaxed text-slate-300">
                {selectedLog?.explanation ||
                  'Click any formatting step to inspect the reason behind the transformation.'}
              </p>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}