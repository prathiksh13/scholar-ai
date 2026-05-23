import { useEffect, useMemo, useRef, useState, forwardRef, useImperativeHandle } from 'react'
import { FileText, Image, Table, Plus, Trash2, Maximize2, Minimize2 } from 'lucide-react'

function countPages(html) {
  if (!html) return 0
  const matches = html.match(/data-page-number="\d+"/g)
  return matches ? matches.length : 0
}

const EditablePreview = forwardRef(({
  html,
  editable = true,
  title = 'Formatted preview',
  format = 'IEEE',
  isFormatting = false,
  zoom = 1, // Zoom scale multiplier
  onChange,
  onSave,
  onBlockSelect, // Notify parent of selected block
}, ref) => {
  const paperRef = useRef(null)
  const imageInputRef = useRef(null)
  const saveTimerRef = useRef(null)
  const [activeKind, setActiveKind] = useState(null)
  const [activeBlockRef, setActiveBlockRef] = useState(null)
  const pageCount = useMemo(() => countPages(html), [html])

  // Expose methods to parent via ref
  useImperativeHandle(ref, () => ({
    addSection: addSectionBlock,
    addImage: addImageBlock,
    addTable: addTableBlock,
    addReference: addReferenceBlock,
    removeBlock: removeActiveBlock,
    addRow: addTableRow,
    addColumn: addTableColumn,
    resize: resizeFigure,
    openImage: openImagePicker,
    activeKind,
    hasSelection: !!activeBlockRef
  }))

  useEffect(() => {
    const root = paperRef.current
    if (!root) return

    if (root.innerHTML !== (html || '')) {
      root.innerHTML = html || ''
    }
    if (!editable) return

    const editableSelectors = [
      '.layout-title',
      '.layout-author',
      '.layout-keyword',
      '.layout-heading',
      '.layout-paragraph',
      '.layout-reference',
      'figcaption',
      'td',
      'th',
    ].join(',')

    root.querySelectorAll(editableSelectors).forEach((node) => {
      node.setAttribute('contenteditable', 'true')
      node.setAttribute('spellcheck', 'false')
    })

    root.querySelectorAll('figure, table').forEach((node) => {
      node.setAttribute('data-editable-block', 'true')
    })
  }, [html, editable])

  const handleInput = () => {
    if (!editable || !paperRef.current) return
    if (saveTimerRef.current) {
      window.clearTimeout(saveTimerRef.current)
    }
    saveTimerRef.current = window.setTimeout(() => {
      onSave?.(paperRef.current?.innerHTML || '')
    }, 700)
  }

  const handleBlur = () => {
    if (!editable || !paperRef.current) return
    if (saveTimerRef.current) {
      window.clearTimeout(saveTimerRef.current)
      saveTimerRef.current = null
    }
    onSave?.(paperRef.current.innerHTML)
  }

  const mutatePreview = (mutator, shouldPersist = true) => {
    if (!paperRef.current) return
    mutator(paperRef.current)
    if (shouldPersist) onSave?.(paperRef.current.innerHTML)
  }

  const parsePxFromStyle = (style = '', key) => {
    const match = style.match(new RegExp(`${key}\\s*:\\s*([\\d.]+)pt`, 'i'))
    return match ? Number(match[1]) : null
  }

  const blockStyleForInsertion = (referenceNode) => {
    const style = referenceNode?.getAttribute('style') || ''
    const left = parsePxFromStyle(style, 'left') ?? 54
    const width = parsePxFromStyle(style, 'width') ?? 252
    const top = parsePxFromStyle(style, 'top') ?? 120
    const minHeight = parsePxFromStyle(style, 'min-height') ?? 80
    return `left:${left}pt;top:${top + minHeight + 12}pt;width:${width}pt;min-height:${Math.max(70, minHeight)}pt;`
  }

  const addSectionBlock = () => {
    if (!paperRef.current) return
    const base = activeBlockRef || paperRef.current.querySelector('.layout-block:last-child')
    const style = blockStyleForInsertion(base)
    mutatePreview((root) => {
      const container = base?.parentElement || root.querySelector('.formatflow-page-surface')
      if (!container) return
      const node = document.createElement('div')
      node.className = 'layout-block layout-heading'
      node.setAttribute('data-kind', 'heading')
      node.setAttribute('data-block-kind', 'heading')
      node.setAttribute('style', style)
      node.innerHTML = '<span contenteditable="true">New Section Heading</span>'
      if (base?.nextSibling) container.insertBefore(node, base.nextSibling)
      else container.appendChild(node)
      
      node.classList.add('is-active')
      setActiveBlockRef(node)
      setActiveKind('heading')
      onBlockSelect?.('heading')
    })
  }

  const addReferenceBlock = () => {
    if (!paperRef.current) return
    const base = activeBlockRef || paperRef.current.querySelector('.layout-block:last-child')
    const style = blockStyleForInsertion(base)
    mutatePreview((root) => {
      const container = base?.parentElement || root.querySelector('.formatflow-page-surface')
      if (!container) return
      const node = document.createElement('div')
      node.className = 'layout-block layout-reference'
      node.setAttribute('data-kind', 'reference')
      node.setAttribute('data-block-kind', 'reference')
      node.setAttribute('style', style)
      node.innerHTML = '<span contenteditable="true">[1] Author, "Reference Title," Journal Name, 2026.</span>'
      if (base?.nextSibling) container.insertBefore(node, base.nextSibling)
      else container.appendChild(node)
      
      node.classList.add('is-active')
      setActiveBlockRef(node)
      setActiveKind('reference')
      onBlockSelect?.('reference')
    })
  }

  const addImageBlock = () => {
    if (!paperRef.current) return
    const base = activeBlockRef || paperRef.current.querySelector('.layout-block:last-child')
    const style = blockStyleForInsertion(base)
    mutatePreview((root) => {
      const container = base?.parentElement || root.querySelector('.formatflow-page-surface')
      if (!container) return
      const node = document.createElement('div')
      node.className = 'layout-block layout-figure'
      node.setAttribute('data-kind', 'figure')
      node.setAttribute('data-block-kind', 'figure')
      node.setAttribute('style', style)
      node.innerHTML = '<figure><div class="figure-placeholder">Figure</div><figcaption contenteditable="true">Figure caption</figcaption></figure>'
      if (base?.nextSibling) container.insertBefore(node, base.nextSibling)
      else container.appendChild(node)
      
      // Focus the new block
      node.classList.add('is-active')
      setActiveBlockRef(node)
      setActiveKind('figure')
      onBlockSelect?.('figure')
    })
  }

  const addTableBlock = () => {
    if (!paperRef.current) return
    const base = activeBlockRef || paperRef.current.querySelector('.layout-block:last-child')
    const style = blockStyleForInsertion(base)
    mutatePreview((root) => {
      const container = base?.parentElement || root.querySelector('.formatflow-page-surface')
      if (!container) return
      const node = document.createElement('div')
      node.className = 'layout-block layout-table'
      node.setAttribute('data-kind', 'table')
      node.setAttribute('data-block-kind', 'table')
      node.setAttribute('style', style)
      node.innerHTML = '<figure class="formatflow-table"><figcaption contenteditable="true">Table caption</figcaption><table><tbody><tr><td contenteditable="true">Cell 1</td><td contenteditable="true">Cell 2</td></tr><tr><td contenteditable="true">Cell 3</td><td contenteditable="true">Cell 4</td></tr></tbody></table></figure>'
      if (base?.nextSibling) container.insertBefore(node, base.nextSibling)
      else container.appendChild(node)

      // Focus the new block
      node.classList.add('is-active')
      setActiveBlockRef(node)
      setActiveKind('table')
      onBlockSelect?.('table')
    })
  }

  const removeActiveBlock = () => {
    if (!activeBlockRef) return
    mutatePreview(() => {
      activeBlockRef.remove()
      setActiveBlockRef(null)
      setActiveKind(null)
      onBlockSelect?.(null)
    })
  }

  const addTableRow = () => {
    if (!activeBlockRef || activeKind !== 'table') return
    mutatePreview(() => {
      const table = activeBlockRef.querySelector('table')
      if (!table) return
      const body = table.tBodies[0] || table.createTBody()
      const cols = table.rows[0]?.cells.length || 2
      const row = body.insertRow(-1)
      for (let i = 0; i < cols; i += 1) {
        const cell = row.insertCell(-1)
        cell.setAttribute('contenteditable', 'true')
        cell.textContent = `Cell ${i + 1}`
      }
    })
  }

  const addTableColumn = () => {
    if (!activeBlockRef || activeKind !== 'table') return
    mutatePreview(() => {
      const table = activeBlockRef.querySelector('table')
      if (!table) return
      Array.from(table.rows).forEach((row) => {
        const cell = row.insertCell(-1)
        cell.setAttribute('contenteditable', 'true')
        cell.textContent = 'Cell'
      })
    })
  }

  const openImagePicker = () => {
    imageInputRef.current?.click()
  }

  const replaceFigureImage = async (event) => {
    const file = event.target.files?.[0]
    if (!file || !activeBlockRef || activeKind !== 'figure') return
    const src = await new Promise((resolve, reject) => {
      const reader = new FileReader()
      reader.onload = () => resolve(reader.result)
      reader.onerror = reject
      reader.readAsDataURL(file)
    })
    mutatePreview(() => {
      const figure = activeBlockRef.querySelector('figure') || activeBlockRef
      let image = figure.querySelector('img')
      if (!image) {
        image = document.createElement('img')
        figure.prepend(image)
      }
      image.src = src
      image.alt = file.name
      const placeholder = figure.querySelector('.figure-placeholder')
      if (placeholder) placeholder.remove()
      let caption = figure.querySelector('figcaption')
      if (!caption) {
        caption = document.createElement('figcaption')
        caption.setAttribute('contenteditable', 'true')
        figure.appendChild(caption)
      }
      if (!caption.textContent?.trim()) caption.textContent = file.name
    })
    event.target.value = ''
  }

  const resizeFigure = (deltaPct) => {
    if (!activeBlockRef || activeKind !== 'figure') return
    mutatePreview(() => {
      const style = activeBlockRef.getAttribute('style') || ''
      const width = parsePxFromStyle(style, 'width') ?? 252
      const next = Math.max(140, Math.min(420, width + deltaPct))
      const updated = style.replace(/width\s*:\s*[\d.]+pt;?/i, `width:${next}pt;`)
      activeBlockRef.setAttribute('style', updated)
    })
  }

  const handleClick = (event) => {
    if (!editable) return
    paperRef.current?.querySelectorAll('.layout-block.is-active').forEach((node) => node.classList.remove('is-active'))
    const block = event.target.closest('.layout-block[data-block-kind]')
    if (!block) {
      setActiveKind(null)
      setActiveBlockRef(null)
      onBlockSelect?.(null)
      return
    }
    block.classList.add('is-active')
    setActiveBlockRef(block)
    const kind = (block.getAttribute('data-block-kind') || '').toLowerCase()
    setActiveKind(kind)
    onBlockSelect?.(kind)
  }

  useEffect(() => () => {
    if (saveTimerRef.current) {
      window.clearTimeout(saveTimerRef.current)
    }
  }, [])

  return (
    <div className="flex h-full min-h-0 flex-col">
      <input ref={imageInputRef} type="file" accept="image/*" className="hidden" onChange={replaceFigureImage} />
      
      <div className="paper-preview-shell flex-1 overflow-visible">
        <div className="paged-preview-stage" style={{ transform: `scale(${zoom})`, transformOrigin: 'top center', transition: 'transform 0.2s cubic-bezier(0.16, 1, 0.3, 1)' }}>
          {html ? (
            <div
              ref={paperRef}
              className="paged-preview-pages formatflow-print-editor"
              data-template={format}
              dangerouslySetInnerHTML={{ __html: html }}
              onInput={handleInput}
              onBlur={handleBlur}
              onClick={handleClick}
            />
          ) : (
            <div className="paged-preview-empty p-8">
              <FileText className="h-10 w-10 text-slate-600 stroke-[1.5]" />
              <p className="mt-4 text-sm font-medium text-slate-500">Awaiting formatted document layout...</p>
              <p className="mt-1 text-xs text-slate-600">Upload a DOCX file to run live template formatting.</p>
            </div>
          )}
        </div>
      </div>
    </div>
  )
})

export default EditablePreview