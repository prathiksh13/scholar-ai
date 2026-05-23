import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { motion } from 'framer-motion'
import { loginWithEmail, loginWithGoogle, registerWithEmail } from '../firebase'
import { Library, Sparkles, Mail, Lock, ArrowLeft } from 'lucide-react'

export default function Login() {
  const navigate = useNavigate()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [isRegister, setIsRegister] = useState(false)
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  const handleSubmit = async (e) => {
    e.preventDefault()
    setError('')
    setLoading(true)
    try {
      if (isRegister) {
        await registerWithEmail(email, password)
      } else {
        await loginWithEmail(email, password)
      }
      navigate('/workspace')
    } catch (err) {
      setError(err.message || 'Authentication failed')
    } finally {
      setLoading(false)
    }
  }

  const handleGoogle = async () => {
    setError('')
    setLoading(true)
    try {
      await loginWithGoogle()
      navigate('/workspace')
    } catch (err) {
      setError(err.message || 'Google sign-in failed')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-[#030712] relative overflow-hidden px-4 select-none">
      {/* Ambient background glows */}
      <div className="absolute top-[30%] left-[20%] w-[50%] h-[50%] rounded-full bg-cyan-900/5 blur-[120px] pointer-events-none" />
      <div className="absolute bottom-[30%] right-[20%] w-[50%] h-[50%] rounded-full bg-teal-900/5 blur-[120px] pointer-events-none" />

      {/* Back button */}
      <Link
        to="/"
        className="absolute top-6 left-6 inline-flex items-center gap-2 text-xs font-medium text-slate-400 hover:text-white transition group"
      >
        <ArrowLeft className="h-3.5 w-3.5 group-hover:-translate-x-0.5 transition-transform" />
        Back to Home
      </Link>

      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.5, cubicBezier: [0.16, 1, 0.3, 1] }}
        className="glass-panel w-full max-w-[420px] rounded-2xl p-8 relative overflow-hidden"
      >
        {/* Ambient Top Glow Border */}
        <div className="absolute top-0 left-0 w-full h-[2px] bg-gradient-to-r from-transparent via-cyan-500/25 to-transparent" />

        {/* Logo / Badge */}
        <div className="flex flex-col items-center text-center">
          <Link to="/" className="flex items-center gap-2 group mb-4">
            <div className="h-7 w-7 rounded-lg bg-gradient-to-tr from-cyan-500 to-teal-400 flex items-center justify-center shadow-md shadow-cyan-500/10">
              <Library className="h-3.5 w-3.5 text-[#030712] stroke-[2.5]" />
            </div>
            <span className="text-base font-bold tracking-tight text-white">
              Scholar<span className="text-cyan-400">AI</span>
            </span>
          </Link>
          <h1 className="text-xl font-medium tracking-tight text-white">
            {isRegister ? 'Create your account' : 'Welcome back'}
          </h1>
          <p className="mt-1.5 text-xs text-slate-400 max-w-[280px]">
            {isRegister ? 'Enter details to start visual formatting' : 'Sign in to access your active workspace'}
          </p>
        </div>

        {error && (
          <motion.p
            initial={{ opacity: 0, scale: 0.95 }}
            animate={{ opacity: 1, scale: 1 }}
            className="mt-5 rounded-lg border border-red-500/10 bg-red-500/5 px-4 py-2.5 text-xs text-red-300 font-medium text-center"
          >
            {error}
          </motion.p>
        )}

        <form onSubmit={handleSubmit} className="mt-6 space-y-4">
          <div>
            <label className="mb-1.5 block text-xs font-medium text-slate-400">Email Address</label>
            <div className="relative">
              <span className="absolute inset-y-0 left-3 flex items-center text-slate-500 pointer-events-none">
                <Mail className="h-3.5 w-3.5" />
              </span>
              <input
                type="email"
                required
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                className="w-full rounded-xl border border-white/5 bg-white/[0.02] pl-9 pr-4 py-2.5 text-sm text-white placeholder-slate-600 outline-none focus:border-cyan-500/40 focus:bg-white/[0.04] transition duration-200"
                placeholder="you@university.edu"
              />
            </div>
          </div>

          <div>
            <label className="mb-1.5 block text-xs font-medium text-slate-400">Password</label>
            <div className="relative">
              <span className="absolute inset-y-0 left-3 flex items-center text-slate-500 pointer-events-none">
                <Lock className="h-3.5 w-3.5" />
              </span>
              <input
                type="password"
                required
                minLength={6}
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                className="w-full rounded-xl border border-white/5 bg-white/[0.02] pl-9 pr-4 py-2.5 text-sm text-white placeholder-slate-600 outline-none focus:border-cyan-500/40 focus:bg-white/[0.04] transition duration-200"
                placeholder="••••••••"
              />
            </div>
          </div>

          <button type="submit" disabled={loading} className="btn-primary w-full mt-2 font-semibold text-xs tracking-wide">
            {loading ? 'Authenticating...' : isRegister ? 'Create Account' : 'Sign In'}
          </button>
        </form>

        <div className="my-5 flex items-center gap-3">
          <div className="h-px flex-1 bg-white/[0.04]" />
          <span className="text-[10px] font-semibold text-slate-500 uppercase tracking-widest">Or Secure Login</span>
          <div className="h-px flex-1 bg-white/[0.04]" />
        </div>

        <button
          type="button"
          onClick={handleGoogle}
          disabled={loading}
          className="btn-secondary w-full text-xs font-medium tracking-wide"
        >
          Continue with Google
        </button>

        <p className="mt-6 text-center text-xs text-slate-400">
          {isRegister ? 'Already registered?' : "Don't have an account yet?"}{' '}
          <button
            type="button"
            onClick={() => {
              setIsRegister(!isRegister)
              setError('')
            }}
            className="font-semibold text-cyan-400 hover:text-cyan-300 transition duration-150"
          >
            {isRegister ? 'Sign In' : 'Sign Up'}
          </button>
        </p>
      </motion.div>
    </div>
  )
}
