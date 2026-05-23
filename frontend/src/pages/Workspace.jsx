import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import {
  FileText,
  Gauge,
  Library,
  LogOut,
  Maximize2,
  Play,
  Upload,
  Wand2,
} from 'lucide-react'
import { logout } from '../firebase'
import { useAuth } from '../context/AuthContext'
import {
  compileLatexSource,
  downloadDocx,
  fetchCompiledPdfBlob,
  getDocument,
  saveEditedHtml,
  saveLatexSource,
  streamFormatting,
  uploadDocument,
} from '../api/client'
import UploadZone from '../components/UploadZone'
import TemplateSelector from '../components/TemplateSelector'
import FormatLogPanel from '../components/FormatLogPanel'
import EditablePreview from '../components/EditablePreview'
import LatexEditor from '../components/LatexEditor'

const FORMAT_OPTIONS = [
  { id: 'IEEE', title: 'IEEE', description: 'Two-column conference format.', badge: 'MVP' },
  { id: 'ACM', title: 'ACM', description: 'Placeholder mapping into IEEE flow.', badge: 'Soon' },
  { id: 'Springer', title: 'Springer', description: 'Future preset shell.', badge: 'Soon' },
  { id: 'Elsevier', title: 'Elsevier', description: 'Future journal preset.', badge: 'Soon' },
]

const PIPELINE_STEPS = [
  { id: 'parse', message: 'Detecting title and structure...' },
  { id: 'abstract', message: 'Detecting abstract block...' },
  { id: 'headings', message: 'Extracting academic headings...' },
  { id: 'margins', message: 'Applying margins (0.75 in)...' },
  { id: 'fonts', message: 'Formatting document fonts...' },
  { id: 'columns', message: 'Arranging columns...' },
  { id: 'figures', message: 'Fitting figures to margins...' },
  { id: 'captions', message: 'Aligning captions...' },
  { id: 'references', message: 'Formatting numeric reference style...' },
  { id: 'compliance', message: 'Running publication sanity pass...' },
]

function mergeLog(list, nextLog) {
  const index = list.findIndex((item) => item.id === nextLog.id)
  if (index === -1) return [...list, nextLog]
  const copy = [...list]
  copy[index] = { ...copy[index], ...nextLog }
  return copy
}

function formatErrorMessage(error) {
  if (!error) return 'Unknown error'
  if (typeof error === 'string') return error
  return error.message || 'Unknown error'
}

export default function Workspace() {
  const { user } = useAuth()
  const streamAbortRef = useRef(null)
  const sidebarResizeRef = useRef(null)
  const splitResizeRef = useRef(null)
  const latexDebounceRef = useRef(null)
  const remoteLatexUpdateRef = useRef(false)
  const pdfUrlRef = useRef('')

  const [file, setFile] = useState(null)
  const [documentId, setDocumentId] = useState(null)
  const [format, setFormat] = useState('IEEE')
  const [title, setTitle] = useState('')
  const [logs, setLogs] = useState([])
  const [selectedLogId, setSelectedLogId] = useState(null)
  const [status, setStatus] = useState('')
  const [compliance, setCompliance] = useState(null)
  const [uploadProgress, setUploadProgress] = useState(0)
  const [isUploading, setIsUploading] = useState(false)
  const [isFormatting, setIsFormatting] = useState(false)
  const [isCompiling, setIsCompiling] = useState(false)
  const [isExporting, setIsExporting] = useState(false)
  const [formatActions, setFormatActions] = useState([])
  const [htmlPreview, setHtmlPreview] = useState('')
  const [latexSource, setLatexSource] = useState('')
  const [compileErrors, setCompileErrors] = useState([])
  const [pdfUrl, setPdfUrl] = useState('')
  const [mode, setMode] = useState('split')
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false)
  const [sidebarWidth, setSidebarWidth] = useState(() => {
    try {
      const saved = localStorage.getItem('latexSidebarWidth')
      return saved ? Number(saved) : 360
    } catch (error) {
      return 360
    }
  })
  const [splitWidth, setSplitWidth] = useState(() => {
    try {
      const saved = localStorage.getItem('latexSplitWidth')
      return saved ? Number(saved) : 560
    } catch (error) {
      return 560
    }
  })

  const selectedLog = useMemo(
    () => logs.find((item) => item.id === selectedLogId) || logs.find((item) => item.status === 'running') || logs[0],
    [logs, selectedLogId],
  )

  const userInitials = useMemo(() => {
    if (!user?.email) return 'SA'
    return user.email.slice(0, 2).toUpperCase()
  }, [user])

  const stopStream = useCallback(() => {
    if (streamAbortRef.current) {
      streamAbortRef.current()
      streamAbortRef.current = null
    }
  }, [])

  const clearPdfUrl = useCallback((nextUrl = '') => {
    if (pdfUrlRef.current) {
      URL.revokeObjectURL(pdfUrlRef.current)
    }
    pdfUrlRef.current = nextUrl
    setPdfUrl(nextUrl)
  }, [])

  const refreshPdf = useCallback(async (docId) => {
    try {
      const blob = await fetchCompiledPdfBlob(docId)
      const nextUrl = URL.createObjectURL(blob)
      clearPdfUrl(nextUrl)
      return nextUrl
    } catch (error) {
      setStatus(formatErrorMessage(error))
      clearPdfUrl('')
      return ''
    }
  }, [clearPdfUrl])

  const syncDocumentBundle = useCallback(async (docId) => {
    let latest = null
    for (let attempt = 0; attempt < 5; attempt += 1) {
      latest = await getDocument(docId)
      if (latest?.latex || latest?.pdf_path) break
      await new Promise((resolve) => window.setTimeout(resolve, 400))
    }

    if (!latest) return

    setTitle(latest.semantic?.title || latest.title || latest.filename || title || '')
    setHtmlPreview(latest.formatted_html || latest.original_html || '')
    setLatexSource(latest.latex || '')
    setCompileErrors(latest.compile_errors || [])
    if (latest.compliance) setCompliance(latest.compliance)
    if (latest.latex) remoteLatexUpdateRef.current = true
    if (latest.pdf_path) {
      await refreshPdf(docId)
    }
  }, [refreshPdf, title])

  const startFormatting = useCallback((docId = documentId, formatName = format) => {
    if (!docId) return

    stopStream()
    setIsFormatting(true)
    setLogs(
      PIPELINE_STEPS.map((step) => ({
        id: step.id,
        message: step.message,
        explanation: 'Running the formatting pipeline...',
        status: 'running',
      })),
    )
    setSelectedLogId('parse')
    setFormatActions([])

    streamAbortRef.current = streamFormatting(docId, formatName, {
      onLog: (log) => {
        setLogs((current) => mergeLog(current, log))
        setSelectedLogId(log.id)
        setStatus(log.message || 'Formatting...')
      },
      onPreview: (payload) => {
        if (payload?.html) setHtmlPreview(payload.html)
        if (payload?.step) setSelectedLogId(payload.step)
        if (payload?.message) setStatus(payload.message)
      },
      onCompliance: (report) => {
        setCompliance(report)
      },
      onComplete: async (payload) => {
        if (payload?.html) setHtmlPreview(payload.html)
        if (payload?.compliance) setCompliance(payload.compliance)
        setFormatActions(payload?.actions || [])
        setLogs((current) => current.map((item) => ({ ...item, status: 'done' })))
        setIsFormatting(false)
        setIsUploading(false)
        setStatus('Formatting complete. LaTeX bundle is ready.')
        await syncDocumentBundle(docId)
        setMode('visual')
      },
      onError: (error) => {
        setIsFormatting(false)
        setIsUploading(false)
        setStatus(error instanceof Error ? error.message : 'Formatting failed')
      },
    })
  }, [documentId, format, stopStream, syncDocumentBundle])

  useEffect(() => () => stopStream(), [stopStream])

  useEffect(() => {
    return () => {
      if (latexDebounceRef.current) window.clearTimeout(latexDebounceRef.current)
      if (pdfUrlRef.current) URL.revokeObjectURL(pdfUrlRef.current)
    }
  }, [])

  useEffect(() => {
    if (!latexSource || !documentId || mode === 'visual') return
    if (remoteLatexUpdateRef.current) {
      remoteLatexUpdateRef.current = false
      return
    }

    if (latexDebounceRef.current) window.clearTimeout(latexDebounceRef.current)
    latexDebounceRef.current = window.setTimeout(async () => {
      setIsCompiling(true)
      try {
        const response = await saveLatexSource(documentId, latexSource)
        if (response?.latex) {
          remoteLatexUpdateRef.current = true
          setLatexSource(response.latex)
        }
        setCompileErrors(response?.compile_errors || [])
        if (response?.semantic?.title) setTitle(response.semantic.title)
        await refreshPdf(documentId)
        setStatus(response?.compile_errors?.length ? 'LaTeX compiled with warnings/errors.' : 'LaTeX compiled successfully.')
      } catch (error) {
        setStatus(formatErrorMessage(error))
      } finally {
        setIsCompiling(false)
      }
    }, 1200)
  }, [latexSource, documentId, mode, refreshPdf])

  const handleFile = (nextFile) => {
    setFile(nextFile)
    setStatus(`Selected ${nextFile.name}. Upload to start formatting.`)
  }

  const handleUpload = async () => {
    if (!file) {
      setStatus('Select a DOCX file first.')
      return
    }

    stopStream()
    setIsUploading(true)
    setUploadProgress(8)
    setStatus('Uploading and parsing DOCX...')

    try {
      const data = await uploadDocument(file, setUploadProgress)
      setDocumentId(data.document_id)
      setTitle(data.semantic?.title || data.title || file.name)
      setMode('visual')
      setHtmlPreview(data.formatted_html || data.original_html || '')
      setLatexSource(data.latex || '')
      setCompileErrors(data.compile_errors || [])
      setCompliance(null)
      setFormatActions([])
      setLogs([])
      setSelectedLogId(null)
      setStatus('Document uploaded. Starting live formatting...')
      startFormatting(data.document_id, format)
      await syncDocumentBundle(data.document_id)
    } catch (error) {
      setStatus(formatErrorMessage(error))
      setIsUploading(false)
    }
  }

  const handleFormatChange = (nextFormat) => {
    setFormat(nextFormat)
    if (documentId && !isFormatting) {
      startFormatting(documentId, nextFormat)
    }
    if (nextFormat === 'IEEE') {
      setMode('visual')
    }
  }

  const compileNow = async () => {
    if (!documentId) return
    setIsCompiling(true)
    try {
      const response = await compileLatexSource(documentId)
      setCompileErrors(response?.compile_errors || [])
      setStatus(response?.compile_errors?.length ? 'LaTeX compiled with warnings/errors.' : 'LaTeX compiled successfully.')
      await refreshPdf(documentId)
    } catch (error) {
      setStatus(formatErrorMessage(error))
    } finally {
      setIsCompiling(false)
    }
  }

  const exportPdf = async () => {
    if (!documentId) return
    setIsExporting(true)
    try {
      const blob = await fetchCompiledPdfBlob(documentId)
      const url = URL.createObjectURL(blob)
      const anchor = document.createElement('a')
      anchor.href = url
      anchor.download = `scholarai_${documentId.slice(0, 8)}.pdf`
      document.body.appendChild(anchor)
      anchor.click()
      anchor.remove()
      URL.revokeObjectURL(url)
      setStatus('PDF download started.')
    } catch (error) {
      setStatus(formatErrorMessage(error))
    } finally {
      setIsExporting(false)
    }
  }

  const exportTex = () => {
    if (!latexSource) return
    const url = URL.createObjectURL(new Blob([latexSource], { type: 'text/x-tex;charset=utf-8' }))
    const anchor = document.createElement('a')
    anchor.href = url
    anchor.download = `scholarai_${documentId?.slice(0, 8) || 'paper'}.tex`
    document.body.appendChild(anchor)
    anchor.click()
    anchor.remove()
    URL.revokeObjectURL(url)
  }

  const handleVisualSave = async (nextHtml) => {
    if (!documentId) return
    if (htmlPreview === nextHtml) return

    try {
      const response = await saveEditedHtml(documentId, nextHtml)
      const refreshedHtml = response?.formatted_html || nextHtml
      setHtmlPreview(refreshedHtml)
      if (response?.latex) {
        remoteLatexUpdateRef.current = true
        setLatexSource(response.latex)
      }
      setCompileErrors(response?.compile_errors || [])
      if (response?.compliance) setCompliance(response.compliance)
      await refreshPdf(documentId)
      setStatus('Preview updated and LaTeX synchronized.')
    } catch (error) {
      setStatus(formatErrorMessage(error))
    }
  }

  const startSidebarDrag = (event) => {
    event.preventDefault()
    const startX = event.clientX
    const startWidth = sidebarWidth
    const onMove = (moveEvent) => {
      const nextWidth = Math.max(260, Math.min(480, startWidth + (moveEvent.clientX - startX)))
      setSidebarWidth(nextWidth)
    }
    const onUp = () => {
      localStorage.setItem('latexSidebarWidth', String(sidebarWidth))
      document.removeEventListener('mousemove', onMove)
      document.removeEventListener('mouseup', onUp)
    }
    document.addEventListener('mousemove', onMove)
    document.addEventListener('mouseup', onUp)
  }

  const startSplitDrag = (event) => {
    event.preventDefault()
    const startX = event.clientX
    const startWidth = splitWidth
    const onMove = (moveEvent) => {
      const containerWidth = splitResizeRef.current?.parentElement?.getBoundingClientRect().width || 1200
      const nextWidth = Math.max(320, Math.min(containerWidth - 360, startWidth + (moveEvent.clientX - startX)))
      setSplitWidth(nextWidth)
    }
    const onUp = () => {
      localStorage.setItem('latexSplitWidth', String(splitWidth))
      document.removeEventListener('mousemove', onMove)
      document.removeEventListener('mouseup', onUp)
    }
    document.addEventListener('mousemove', onMove)
    document.addEventListener('mouseup', onUp)
  }

  const sidebarStyle = sidebarCollapsed ? { width: '72px' } : { width: `${sidebarWidth}px` }

  return (
    <div className="min-h-screen bg-[#030712] text-white">
      <header className="glass sticky top-0 z-40 border-b border-white/5">
        <div className="mx-auto flex max-w-[1800px] items-center justify-between px-5 py-4">
          <Link to="/" className="flex items-center gap-2 group">
            <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-gradient-to-tr from-cyan-500 to-teal-400 shadow-lg shadow-cyan-500/15 transition group-hover:scale-105">
              <Library className="h-4 w-4 text-[#030712]" />
            </div>
            <span className="text-base font-bold tracking-tight text-white">
              Scholar<span className="text-cyan-400">AI</span>
            </span>
          </Link>

          <div className="flex flex-wrap items-center gap-2">
            <button type="button" className={`analysis-btn ${mode === 'visual' ? 'active' : ''}`} onClick={() => setMode('visual')}>Visual Editor</button>
            <button type="button" className={`analysis-btn ${mode === 'latex' ? 'active' : ''}`} onClick={() => setMode('latex')}>Show LaTeX</button>
            <button type="button" className={`analysis-btn ${mode === 'split' ? 'active' : ''}`} onClick={() => setMode('split')}>Split View</button>
            <button type="button" className="analysis-btn" onClick={compileNow} disabled={!documentId || isCompiling || isUploading || isFormatting}>
              <Play className="h-3.5 w-3.5" />
              Compile
            </button>
            <button type="button" className="analysis-btn" onClick={exportTex} disabled={!latexSource}>Export TEX</button>
            <button type="button" className="analysis-btn" onClick={exportPdf} disabled={!documentId || isExporting || isCompiling}>Export PDF</button>
            <button type="button" onClick={logout} className="btn-secondary py-2 px-3 text-sm">
              <LogOut className="h-4 w-4" />
              Logout
            </button>
          </div>
        </div>
      </header>

      <main className="workspace-shell mx-auto max-w-[1800px] px-4 lg:px-6">
        {status && (
          <div className="workspace-statusbar rounded-2xl border border-cyan-500/20 bg-cyan-500/10 px-4 py-3 text-sm text-cyan-100">
            {status}
          </div>
        )}

        <div className="workspace-panels latex-layout-shell">
          <aside className={`workspace-left latex-sidebar ${sidebarCollapsed ? 'is-collapsed' : ''}`} style={sidebarStyle}>
            <div className="glass-strong rounded-3xl p-4">
              <div className="flex items-center justify-between gap-3">
                <div>
                  <p className="text-xs uppercase tracking-[0.25em] text-slate-400">Upload</p>
                  {!sidebarCollapsed && <p className="mt-1 text-xs text-slate-500">DOCX upload with live sync.</p>}
                </div>
                <button type="button" className="btn-secondary px-3 py-2 text-xs" onClick={() => setSidebarCollapsed((value) => !value)}>
                  {sidebarCollapsed ? 'Expand' : 'Collapse'}
                </button>
              </div>

              {!sidebarCollapsed && (
                <>
                  <div className="mt-4">
                    <UploadZone file={file} loading={isUploading} progress={uploadProgress} onFile={handleFile} onClear={() => setFile(null)} />
                  </div>
                  <button type="button" onClick={handleUpload} disabled={!file || isUploading} className="btn-primary mt-4 w-full disabled:opacity-40">
                    <Upload className="h-4 w-4" />
                    Upload & Sync
                  </button>
                </>
              )}
            </div>

            {!sidebarCollapsed && (
              <>
                <div className="glass-strong rounded-3xl p-4">
                  <div className="flex items-center justify-between gap-3">
                    <div>
                      <p className="text-xs uppercase tracking-[0.25em] text-slate-400">Templates</p>
                      <p className="mt-1 text-xs text-slate-500">IEEE is wired end-to-end.</p>
                    </div>
                    <Gauge className="h-4 w-4 text-cyan-300" />
                  </div>
                  <div className="mt-4">
                    <TemplateSelector value={format} onChange={handleFormatChange} options={FORMAT_OPTIONS} />
                  </div>
                </div>

                <div className="glass-strong rounded-3xl p-4">
                  <div className="flex items-center justify-between gap-3">
                    <div>
                      <p className="text-xs uppercase tracking-[0.25em] text-slate-400">Latex Sync</p>
                      <p className="mt-1 text-xs text-slate-500">Auto-compile after edits.</p>
                    </div>
                    <Wand2 className="h-4 w-4 text-cyan-300" />
                  </div>
                  <div className="mt-4 grid gap-2">
                    <button type="button" className="analysis-btn justify-start" onClick={() => setMode('latex')}>Show LaTeX</button>
                    <button type="button" className="analysis-btn justify-start" onClick={() => setMode('split')}>Split View</button>
                    <button type="button" className="analysis-btn justify-start" onClick={compileNow}>Compile Now</button>
                  </div>
                </div>

                <div className="glass-strong rounded-3xl p-4">
                  <FormatLogPanel
                    logs={logs}
                    selectedLogId={selectedLogId}
                    onSelectLog={setSelectedLogId}
                    activeFormat={format}
                    selectedLog={selectedLog}
                  />
                </div>

                <div className="glass-strong rounded-3xl p-4">
                  <div className="flex items-center justify-between gap-3">
                    <div>
                      <p className="text-xs uppercase tracking-[0.25em] text-slate-400">Compile Errors</p>
                      <p className="mt-1 text-xs text-slate-500">Line-numbered feedback from the LaTeX engine.</p>
                    </div>
                    <FileText className="h-4 w-4 text-slate-500" />
                  </div>
                  <div className="mt-4 space-y-2 max-h-[240px] overflow-auto pr-1">
                    {compileErrors.length > 0 ? compileErrors.map((item, index) => (
                      <div key={`${item.line}-${index}`} className={`rounded-xl border p-3 text-xs ${item.severity === 'warning' ? 'border-amber-500/20 bg-amber-500/5' : 'border-red-500/20 bg-red-500/5'}`}>
                        <div className="flex items-center justify-between gap-2 text-[10px] uppercase tracking-[0.22em] text-slate-400">
                          <span>Line {item.line || '0'}</span>
                          <span>{item.severity || 'error'}</span>
                        </div>
                        <p className="mt-2 text-slate-200">{item.message}</p>
                      </div>
                    )) : (
                      <div className="rounded-xl border border-white/10 bg-white/5 p-3 text-xs text-slate-400">No compile errors reported yet.</div>
                    )}
                  </div>
                </div>
              </>
            )}
          </aside>

          <div className="resize-handle-h" ref={sidebarResizeRef} onMouseDown={startSidebarDrag} role="separator" aria-orientation="vertical" />

          <section className="workspace-right latex-main-pane">
            <div className="workspace-preview-pane glass-strong rounded-[28px] latex-preview-shell">
              <div className="preview-header">
                <div>
                  <p className="text-[10px] uppercase tracking-[0.35em] text-cyan-300/60">DOCUMENT WORKSPACE</p>
                  <h2 className="mt-1 text-xl font-semibold text-white">{title || 'IEEE Paper Preview'}</h2>
                  <p className="mt-1 text-sm text-slate-400">{mode === 'latex' ? 'Edit LaTeX directly.' : mode === 'split' ? 'LaTeX editor on the left, PDF on the right.' : 'Edit the visual block layout.'}</p>
                </div>

                <div className="flex items-center gap-2">
                  <span className="preview-badge">{format}</span>
                  {(isFormatting || isCompiling) && <span className="preview-live">Live</span>}
                </div>
              </div>

              <div className="latex-workspace-body">
                {(mode === 'latex' || mode === 'split') && (
                  <div className="latex-editor-column" style={mode === 'split' ? { width: `${splitWidth}px` } : undefined}>
                    <div className="latex-editor-toolbar">
                      <div>
                        <p className="text-[10px] uppercase tracking-[0.28em] text-slate-400">LaTeX Source</p>
                        <p className="text-xs text-slate-500">Live sync, syntax highlighting, auto compile.</p>
                      </div>
                      <div className="flex items-center gap-2">
                        <button type="button" className="analysis-btn" onClick={compileNow} disabled={!documentId || isCompiling}>Compile</button>
                        <button type="button" className="analysis-btn" onClick={() => setMode('visual')}>Visual</button>
                      </div>
                    </div>
                    <div className="latex-editor-surface">
                      <LatexEditor value={latexSource} onChange={(value) => setLatexSource(value)} height="100%" />
                    </div>
                  </div>
                )}

                {mode === 'split' && (
                  <div className="resize-handle-v" ref={splitResizeRef} onMouseDown={startSplitDrag} role="separator" aria-orientation="vertical" />
                )}

                <div className="latex-preview-column">
                  {mode === 'visual' ? (
                    <div className="visual-editor-shell">
                      <EditablePreview
                        html={htmlPreview}
                        editable={!isFormatting}
                        title={title || 'Formatted preview'}
                        format={format}
                        isFormatting={isFormatting}
                        onSave={handleVisualSave}
                      />
                    </div>
                  ) : (
                    <div className="pdf-frame-shell">
                      {pdfUrl ? (
                        <iframe title="Live PDF preview" src={pdfUrl} className="latex-pdf-frame" />
                      ) : (
                        <div className="pdf-placeholder">
                          <Maximize2 className="h-10 w-10 text-cyan-300/60" />
                          <p className="mt-3 text-sm text-slate-300">Compile the document to preview the PDF here.</p>
                        </div>
                      )}
                    </div>
                  )}
                </div>
              </div>
            </div>

            {mode === 'visual' && (
              <div className="mt-4 rounded-3xl border border-white/10 bg-white/[0.02] p-4 text-sm text-slate-400">
                Visual mode edits the rendered blocks, then synchronizes the semantic model and LaTeX source on save.
              </div>
            )}
          </section>
        </div>
      </main>
    </div>
  )
}