import { Link } from 'react-router-dom'
import { motion } from 'framer-motion'
import { FileText, Sparkles, Download, Shield, ArrowRight, Library, LayoutTemplate } from 'lucide-react'

const features = [
  {
    icon: Sparkles,
    title: 'AI Layout Auto-Tune',
    desc: 'Semantically parses content, aligning titles, columns, and figures to template rules instantly.',
    color: 'from-cyan-400 to-blue-500'
  },
  {
    icon: LayoutTemplate,
    title: 'Academic Presets',
    desc: 'Ready-to-publish templates for IEEE, ACM, Springer, Elsevier, and major formatting structures.',
    color: 'from-teal-400 to-emerald-500'
  },
  {
    icon: Download,
    title: 'Double Export',
    desc: 'Export beautifully generated, high-compliance DOCX and camera-ready PDF files instantly.',
    color: 'from-purple-400 to-indigo-500'
  },
  {
    icon: Shield,
    title: 'Safe Processing',
    desc: 'Your papers remain securely processed. All formatting traces run under secure sandboxed environments.',
    color: 'from-pink-400 to-rose-500'
  },
]

const formats = ['IEEE Conference', 'ACM Siggraph', 'Springer Nature', 'Elsevier SSRN', 'APA 7th Edition', 'MLA 9th Edition', 'Chicago Manual']

export default function Landing() {
  return (
    <div className="min-h-screen bg-[#030712] relative overflow-hidden select-none">
      {/* Ambient Radial Glows */}
      <div className="absolute top-[-20%] left-[-10%] w-[60%] h-[60%] rounded-full bg-cyan-900/10 blur-[150px] pointer-events-none" />
      <div className="absolute bottom-[-20%] right-[-10%] w-[60%] h-[60%] rounded-full bg-teal-900/10 blur-[150px] pointer-events-none" />

      {/* Floating Glass Navbar */}
      <nav className="glass-nav sticky top-0 z-50">
        <div className="mx-auto max-w-7xl flex items-center justify-between px-6 py-4">
          <Link to="/" className="flex items-center gap-2 group">
            <div className="h-8 w-8 rounded-lg bg-gradient-to-tr from-cyan-500 to-teal-400 flex items-center justify-center shadow-lg shadow-cyan-500/20 group-hover:scale-105 transition-all">
              <Library className="h-4 w-4 text-[#030712] stroke-[2.5]" />
            </div>
            <span className="text-lg font-bold tracking-tight text-white group-hover:opacity-90 transition">
              Scholar<span className="text-cyan-400">AI</span>
            </span>
          </Link>

          <div className="hidden items-center gap-8 text-sm text-slate-400 md:flex">
            <a href="#features" className="hover:text-white transition duration-200">Features</a>
            <a href="#formats" className="hover:text-white transition duration-200">Supported Formats</a>
          </div>

          <div className="flex items-center gap-4">
            <Link to="/login" className="text-sm font-medium text-slate-300 hover:text-white transition">
              Sign In
            </Link>
            <Link to="/workspace" className="btn-primary py-2 px-4 text-xs font-semibold">
              Launch Workspace
            </Link>
          </div>
        </div>
      </nav>

      {/* Hero Section */}
      <section className="relative mx-auto max-w-5xl px-6 pt-24 pb-16 text-center md:pt-32">
        <motion.div
          initial={{ opacity: 0, y: 15 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6 }}
          className="inline-flex items-center gap-2 rounded-full border border-cyan-500/25 bg-cyan-950/20 px-4 py-1.5 text-xs font-medium tracking-wide text-cyan-300"
        >
          <Sparkles className="h-3 w-3" />
          Academic Layout Optimization
        </motion.div>

        <motion.h1
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6, delay: 0.15 }}
          className="mx-auto mt-6 max-w-4xl text-5xl font-semibold leading-[1.1] tracking-tight text-white md:text-7xl"
        >
          Format research papers <br />
          <span className="gradient-text">instantly with absolute precision</span>
        </motion.h1>

        <motion.p
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6, delay: 0.3 }}
          className="mx-auto mt-8 max-w-2xl text-lg md:text-xl leading-relaxed text-slate-400"
        >
          Upload your document, select a template, and watch the semantic AI engine align sections, margins, figures, and references live.
        </motion.p>

        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6, delay: 0.4 }}
          className="mt-10 flex flex-wrap items-center justify-center gap-4"
        >
          <Link to="/workspace" className="btn-primary px-6 py-3 font-semibold text-sm">
            Start Formatting
            <ArrowRight className="h-4 w-4" />
          </Link>
          <Link to="/login" className="btn-secondary px-6 py-3 font-semibold text-sm">
            Create Account
          </Link>
        </motion.div>
      </section>

      {/* Grid Features */}
      <section id="features" className="mx-auto max-w-7xl px-6 py-24 border-t border-white/[0.03]">
        <div className="text-center max-w-3xl mx-auto mb-16">
          <h2 className="text-3xl font-semibold tracking-tight text-white md:text-4xl">Engineered for Academic Rigor</h2>
          <p className="mt-4 text-slate-400">Forget double-column layout shifts and broken reference numbers. Let AI stream professional presets.</p>
        </div>

        <div className="grid gap-6 sm:grid-cols-2 lg:grid-cols-4">
          {features.map(({ icon: Icon, title, desc, color }, idx) => (
            <motion.div
              initial={{ opacity: 0, y: 25 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true }}
              transition={{ duration: 0.5, delay: idx * 0.1 }}
              key={title}
              className="glass-card rounded-2xl p-6 relative group hover:shadow-2xl hover:shadow-cyan-500/[0.02]"
            >
              <div className="absolute top-0 left-0 w-full h-[2px] rounded-t-2xl bg-gradient-to-r from-transparent via-cyan-500/20 to-transparent opacity-0 group-hover:opacity-100 transition-all duration-300" />
              <div className="mb-5 inline-flex p-3 rounded-xl bg-white/[0.02] border border-white/5 text-slate-300 group-hover:text-cyan-400 group-hover:border-cyan-500/20 group-hover:bg-cyan-950/20 transition-all duration-300">
                <Icon className="h-5 w-5" />
              </div>
              <h3 className="mb-2 font-medium text-white text-base tracking-tight">{title}</h3>
              <p className="text-sm leading-relaxed text-slate-400 group-hover:text-slate-300 transition duration-300">{desc}</p>
            </motion.div>
          ))}
        </div>
      </section>

      {/* Formats Showcase */}
      <section id="formats" className="mx-auto max-w-7xl px-6 py-24 border-t border-white/[0.03] text-center">
        <div className="max-w-2xl mx-auto mb-12">
          <h2 className="text-3xl font-semibold tracking-tight text-white">Supported Templates</h2>
          <p className="mt-3 text-slate-400 text-sm">One source document to any publication style. Mapped to layout specs instantly.</p>
        </div>
        <div className="flex flex-wrap justify-center gap-3">
          {formats.map((f, idx) => (
            <motion.span
              initial={{ opacity: 0, scale: 0.95 }}
              whileInView={{ opacity: 1, scale: 1 }}
              viewport={{ once: true }}
              transition={{ duration: 0.3, delay: idx * 0.05 }}
              key={f}
              className="px-5 py-2.5 rounded-full text-xs font-medium text-cyan-200/90 border border-cyan-500/10 bg-cyan-950/10 hover:border-cyan-500/30 hover:text-white transition duration-200 cursor-default"
            >
              {f}
            </motion.span>
          ))}
        </div>
      </section>

      {/* Footer */}
      <footer className="py-12 border-t border-white/[0.03] text-center text-xs text-slate-500">
        <p className="font-semibold text-slate-300 text-sm tracking-tight">ScholarAI</p>
        <p className="mt-1">Perfect Academic Typesetting Workspace</p>
        <p className="mt-6">&copy; {new Date().getFullYear()} ScholarAI. All rights reserved.</p>
      </footer>
    </div>
  )
}
