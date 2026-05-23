const DEFAULT_OPTIONS = [
  {
    id: 'IEEE',
    title: 'IEEE',
    description: 'Fully functional MVP with live semantic parsing and two-column formatting.',
    badge: 'MVP',
  },
  {
    id: 'ACM',
    title: 'ACM',
    description: 'Selectable now and mapped to the same pipeline until the ACM rule pack ships.',
    badge: 'Soon',
  },
  {
    id: 'Springer',
    title: 'Springer',
    description: 'Future journal preset with the same editable workspace shell.',
    badge: 'Soon',
  },
  {
    id: 'Elsevier',
    title: 'Elsevier',
    description: 'Roadmap template for publication-ready journal formatting.',
    badge: 'Soon',
  },
  {
    id: 'APA',
    title: 'APA',
    description: 'Reference-heavy academic formatting preset for future releases.',
    badge: 'Soon',
  },
  {
    id: 'MLA',
    title: 'MLA',
    description: 'Humanities-focused format preset in the same scalable rule engine.',
    badge: 'Soon',
  },
  {
    id: 'Chicago',
    title: 'Chicago',
    description: 'A future preset for long-form, footnote-heavy papers.',
    badge: 'Soon',
  },
  {
    id: 'Custom',
    title: 'Custom template',
    description: 'Future uploadable ruleset for house styles and lab templates.',
    badge: 'Future',
  },
]

export default function TemplateSelector({ value, onChange, options = DEFAULT_OPTIONS }) {
  return (
    <div className="grid gap-3 sm:grid-cols-2">
      {options.map((option) => {
        const active = value === option.id
        return (
          <button
            key={option.id}
            type="button"
            onClick={() => onChange?.(option.id)}
            className={`format-card ${active ? 'is-active' : ''}`}
          >
            <div className="flex items-center justify-between gap-3">
              <span className="text-sm font-semibold text-white">{option.title}</span>
              <span className={`text-[10px] font-semibold uppercase tracking-[0.3em] ${active ? 'text-cyan-100' : 'text-slate-500'}`}>
                {option.badge}
              </span>
            </div>
            <p className="mt-2 text-left text-xs leading-relaxed text-slate-400">{option.description}</p>
          </button>
        )
      })}
    </div>
  )
}