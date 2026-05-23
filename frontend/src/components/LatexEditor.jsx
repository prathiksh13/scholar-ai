import { useMemo, useRef } from 'react'

export default function LatexEditor({ value, onChange, height = '100%', readOnly = false }) {
  const textareaRef = useRef(null)

  const lineNumbers = useMemo(() => {
    const count = Math.max(1, (value || '').split('\n').length)
    return Array.from({ length: count }, (_, index) => String(index + 1))
  }, [value])

  const handleScroll = (event) => {
    const sibling = event.currentTarget.parentElement?.querySelector('.latex-line-numbers')
    if (sibling) sibling.scrollTop = event.currentTarget.scrollTop
  }

  return (
    <div className="latex-editor-root" style={{ height }}>
      <div className="latex-editor-chrome">
        <div className="latex-line-numbers" aria-hidden="true">
          {lineNumbers.map((line) => (
            <div key={line} className="latex-line-number">{line}</div>
          ))}
        </div>
        <textarea
          ref={textareaRef}
          className="latex-editor-textarea"
          spellCheck={false}
          value={value}
          readOnly={readOnly}
          onChange={(event) => onChange?.(event.target.value)}
          onScroll={handleScroll}
          placeholder="Write LaTeX here..."
        />
      </div>
    </div>
  )
}