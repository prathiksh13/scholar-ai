import { useRef, useState } from 'react'
import { FileText, Upload, X } from 'lucide-react'

function formatBytes(bytes) {
  if (!bytes) return '0 KB'
  const units = ['B', 'KB', 'MB']
  let value = bytes
  let unit = 0
  while (value >= 1024 && unit < units.length - 1) {
    value /= 1024
    unit += 1
  }
  return `${value.toFixed(value >= 10 || unit === 0 ? 0 : 1)} ${units[unit]}`
}

function UploadButtonIcon() {
  return <Upload className="h-4 w-4" />
}

export default function UploadZone({ file, loading = false, progress = 0, onFile, onClear }) {
  const inputRef = useRef(null)
  const [dragActive, setDragActive] = useState(false)

  const openPicker = () => {
    if (loading) return
    inputRef.current?.click()
  }

  const acceptFile = (nextFile) => {
    if (!nextFile) return
    if (!nextFile.name.toLowerCase().endsWith('.docx')) return
    onFile?.(nextFile)
  }

  return (
    <div
      role="button"
      tabIndex={0}
      onClick={openPicker}
      onKeyDown={(event) => {
        if (event.key === 'Enter' || event.key === ' ') openPicker()
      }}
      onDragEnter={(event) => {
        event.preventDefault()
        setDragActive(true)
      }}
      onDragLeave={(event) => {
        event.preventDefault()
        setDragActive(false)
      }}
      onDragOver={(event) => event.preventDefault()}
      onDrop={(event) => {
        event.preventDefault()
        setDragActive(false)
        acceptFile(event.dataTransfer.files?.[0])
      }}
      className={`upload-dropzone ${dragActive ? 'is-dragging' : ''} ${loading ? 'is-loading' : ''}`}
    >
      <input
        ref={inputRef}
        type="file"
        accept=".docx,application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        className="hidden"
        onChange={(event) => acceptFile(event.target.files?.[0])}
      />

      <div className="flex items-start gap-3">
        <div className="rounded-2xl border border-cyan-500/15 bg-cyan-500/10 p-3 text-cyan-200">
          <Upload className="h-5 w-5" />
        </div>
        <div className="min-w-0 flex-1">
          <p className="text-sm font-medium text-white">
            Drag and drop a DOCX or click to browse
          </p>
          <p className="mt-1 text-xs leading-relaxed text-slate-500">
            The formatter reads the semantic structure first, then streams IEEE actions live.
          </p>
        </div>
      </div>

      <div className="mt-4 rounded-2xl border border-white/10 bg-white/5 p-4">
        {file ? (
          <div className="flex items-start justify-between gap-3">
            <div className="min-w-0">
              <div className="flex items-center gap-2 text-sm font-medium text-white">
                <FileText className="h-4 w-4 text-cyan-300" />
                <span className="truncate">{file.name}</span>
              </div>
              <p className="mt-1 text-xs text-slate-500">{formatBytes(file.size)}</p>
            </div>
            <button
              type="button"
              className="rounded-full border border-white/10 bg-white/5 p-2 text-slate-300 transition hover:bg-white/10"
              onClick={(event) => {
                event.stopPropagation()
                onClear?.()
                if (inputRef.current) inputRef.current.value = ''
              }}
            >
              <X className="h-4 w-4" />
            </button>
          </div>
        ) : (
          <p className="text-xs text-slate-500">No file selected yet.</p>
        )}
      </div>

      <div className="mt-4">
        <div className="flex items-center justify-between text-xs text-slate-500">
          <span>{loading ? 'Uploading...' : 'Ready for DOCX upload'}</span>
          <span>{progress}%</span>
        </div>
        <div className="mt-2 h-2 overflow-hidden rounded-full bg-white/5">
          <div
            className="h-full rounded-full bg-gradient-to-r from-cyan-500 to-teal-400 transition-all duration-200"
            style={{ width: `${loading || progress > 0 ? progress : 0}%` }}
          />
        </div>
      </div>
    </div>
  )
}

UploadZone.ButtonIcon = UploadButtonIcon