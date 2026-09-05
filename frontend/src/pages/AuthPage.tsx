import React, { useState, useEffect } from 'react'
import { motion } from 'framer-motion'
import { Link, useNavigate, useLocation } from 'react-router-dom'
import { Mail, Lock, User as UserIcon, ArrowRight, Sparkles, Brain, BookOpen, Clock } from 'lucide-react'
import { useAuthStore } from '../stores/useAuthStore'
import { supabase } from '../lib/supabaseClient'
import { friendlyError } from '../lib/errorCopy'
import { FOCUS_RING } from '../components/ui/shared'

interface AuthPageProps {
  defaultMode?: 'login' | 'signup'
}

export function AuthPage({ defaultMode = 'login' }: AuthPageProps) {
  const navigate = useNavigate()
  const location = useLocation()
  const { user, token } = useAuthStore()

  const [mode, setMode] = useState<'login' | 'signup'>(defaultMode)
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [fullName, setFullName] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [info, setInfo] = useState('')

  // Determine redirect target
  const from = (location.state as { from?: { pathname: string } })?.from?.pathname || '/app'

  useEffect(() => {
    if (user && token) {
      navigate(from, { replace: true })
    }
  }, [user, token, navigate, from])

  useEffect(() => {
    setMode(defaultMode)
  }, [defaultMode])

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError('')
    setInfo('')
    setLoading(true)

    try {
      if (mode === 'signup') {
        const { data, error: signUpError } = await supabase.auth.signUp({
          email,
          password,
          options: { data: { full_name: fullName || email.split('@')[0] } },
        })
        if (signUpError) throw signUpError
        if (!data.session) {
          setInfo('Check your inbox — we sent a confirmation link to activate your account.')
        } else {
          navigate(from, { replace: true })
        }
      } else {
        const { error: signInError } = await supabase.auth.signInWithPassword({ email, password })
        if (signInError) throw signInError
        navigate(from, { replace: true })
      }
    } catch (err: unknown) {
      setError(friendlyError(err) || 'Failed to authenticate. Please check your credentials.')
    } finally {
      setLoading(false)
    }
  }

  const handleGoogleAuth = async () => {
    setError('')
    setLoading(true)
    try {
      const { error: oAuthError } = await supabase.auth.signInWithOAuth({
        provider: 'google',
        options: { redirectTo: `${window.location.origin}${from}` },
      })
      if (oAuthError) throw oAuthError
    } catch (err: unknown) {
      setError(friendlyError(err) || 'Google sign-in is not configured yet.')
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen bg-nb text-nt font-sans selection:bg-npb selection:text-npt flex flex-col justify-center py-12 sm:px-6 lg:px-8 relative overflow-hidden">
      {/* Blueprint grid background */}
      <div
        aria-hidden="true"
        className="absolute inset-0 pointer-events-none opacity-40 z-0"
        style={{
          backgroundImage: `linear-gradient(to right, var(--color-grid) 1px, transparent 1px), linear-gradient(to bottom, var(--color-grid) 1px, transparent 1px)`,
          backgroundSize: '32px 32px',
        }}
      />

      <div className="sm:mx-auto sm:w-full sm:max-w-md relative z-10">
        <div className="text-center mb-6">
          <Link to="/" className="inline-flex items-center gap-2 mb-4 group">
            <span className="font-serif font-black text-28 tracking-tight text-nt group-hover:text-np transition-colors">
              Nor<span className="text-np">AI</span>
            </span>
          </Link>
          <div className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full bg-npb text-npt font-mono text-11 font-medium mb-3">
            <Sparkles size={12} className="text-np" />
            <span>Autonomous Lecture Intelligence</span>
          </div>
          <h1 className="text-24 font-bold font-serif text-nt">
            {mode === 'login' ? 'Sign in to your account' : 'Create your free account'}
          </h1>
          <p className="text-13 text-nt2 mt-1">
            {mode === 'login'
              ? 'Access your processed lectures, study notes, and Nora AI Tutor'
              : 'Includes 45 minutes free lecture processing quota and interactive AI tutoring'}
          </p>
        </div>

        {/* Feature Highlights on Signup */}
        {mode === 'signup' && (
          <div className="mb-6 p-4 rounded-lg bg-ns border border-bdr grid grid-cols-3 gap-2 text-center">
            <div className="flex flex-col items-center gap-1">
              <Clock size={16} className="text-np" />
              <span className="font-mono text-10 uppercase text-nt font-bold">45 Mins Free</span>
              <span className="text-10 text-nt3">Trial Quota</span>
            </div>
            <div className="flex flex-col items-center gap-1">
              <Brain size={16} className="text-np" />
              <span className="font-mono text-10 uppercase text-nt font-bold">AI Tutor</span>
              <span className="text-10 text-nt3">Lecture-Grounded</span>
            </div>
            <div className="flex flex-col items-center gap-1">
              <BookOpen size={16} className="text-np" />
              <span className="font-mono text-10 uppercase text-nt font-bold">Full Notes</span>
              <span className="text-10 text-nt3">Flashcards & Quiz</span>
            </div>
          </div>
        )}

        {/* Form Container */}
        <motion.div
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.2 }}
          className="bg-nb border border-bdr rounded-lg p-6 sm:p-8 shadow-bp"
        >
          {/* Segmented Control */}
          <div className="grid grid-cols-2 p-1 bg-ns2 rounded mb-6 border border-bdr font-display text-11 uppercase font-semibold">
            <button
              onClick={() => setMode('login')}
              className={`py-2 rounded transition-all cursor-pointer ${FOCUS_RING} ${
                mode === 'login'
                  ? 'bg-ns text-np shadow-xs'
                  : 'text-nt3 hover:text-nt'
              }`}
            >
              Sign In
            </button>
            <button
              onClick={() => setMode('signup')}
              className={`py-2 rounded transition-all cursor-pointer ${FOCUS_RING} ${
                mode === 'signup'
                  ? 'bg-ns text-np shadow-xs'
                  : 'text-nt3 hover:text-nt'
              }`}
            >
              Create Account
            </button>
          </div>

          {/* Messages */}
          {error && (
            <div className="mb-4 p-3 rounded bg-nrb border border-nrbr text-nrt text-12" role="alert">
              {error}
            </div>
          )}
          {info && (
            <div className="mb-4 p-3 rounded bg-npb border border-npbr text-npt text-12" role="status">
              {info}
            </div>
          )}

          {/* Form */}
          <form onSubmit={handleSubmit} className="space-y-4">
            {mode === 'signup' && (
              <div>
                <label htmlFor="auth-name" className="block text-10 font-medium font-mono uppercase text-nt3 mb-1">
                  Full Name
                </label>
                <div className="relative">
                  <UserIcon size={15} className="absolute left-3 top-1/2 -translate-y-1/2 text-nt3" />
                  <input
                    id="auth-name"
                    type="text"
                    required
                    value={fullName}
                    onChange={(e) => setFullName(e.target.value)}
                    placeholder="Alex Morgan"
                    className={`w-full pl-9 pr-3 py-2.5 text-13 bg-ns border border-bdr rounded focus:border-np focus:outline-hidden transition-colors ${FOCUS_RING}`}
                  />
                </div>
              </div>
            )}

            <div>
              <label htmlFor="auth-email-input" className="block text-10 font-medium font-mono uppercase text-nt3 mb-1">
                Email Address
              </label>
              <div className="relative">
                <Mail size={15} className="absolute left-3 top-1/2 -translate-y-1/2 text-nt3" />
                <input
                  id="auth-email-input"
                  type="email"
                  required
                  autoComplete="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  placeholder="alex@university.edu"
                  className={`w-full pl-9 pr-3 py-2.5 text-13 bg-ns border border-bdr rounded focus:border-np focus:outline-hidden transition-colors ${FOCUS_RING}`}
                />
              </div>
            </div>

            <div>
              <label htmlFor="auth-password-input" className="block text-10 font-medium font-mono uppercase text-nt3 mb-1">
                Password
              </label>
              <div className="relative">
                <Lock size={15} className="absolute left-3 top-1/2 -translate-y-1/2 text-nt3" />
                <input
                  id="auth-password-input"
                  type="password"
                  required
                  autoComplete={mode === 'signup' ? 'new-password' : 'current-password'}
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="••••••••"
                  className={`w-full pl-9 pr-3 py-2.5 text-13 bg-ns border border-bdr rounded focus:border-np focus:outline-hidden transition-colors ${FOCUS_RING}`}
                />
              </div>
            </div>

            <button
              type="submit"
              disabled={loading}
              className="w-full py-3 px-4 bg-np hover:bg-nph text-npfg font-display text-12 font-semibold uppercase tracking-wider rounded shadow-bp flex items-center justify-center gap-2 transition-colors disabled:opacity-50 disabled:pointer-events-none cursor-pointer active:translate-y-[1px]"
            >
              {loading ? (
                <span>Authenticating...</span>
              ) : (
                <>
                  <span>{mode === 'login' ? 'Sign In to Workspace' : 'Start Free (45m Quota)'}</span>
                  <ArrowRight size={15} />
                </>
              )}
            </button>
          </form>

          {/* Divider */}
          <div className="relative my-6 text-center">
            <div className="absolute inset-0 flex items-center">
              <div className="w-full border-t border-bdr"></div>
            </div>
            <span className="relative px-3 bg-nb text-10 font-medium font-mono uppercase text-nt3">
              OR CONTINUE WITH
            </span>
          </div>

          {/* Google SSO */}
          <button
            onClick={handleGoogleAuth}
            disabled={loading}
            className={`w-full py-2.5 px-4 bg-ns border border-bdr hover:bg-ns2 text-nt font-display text-11 font-medium uppercase tracking-wider rounded flex items-center justify-center gap-2 transition-colors cursor-pointer disabled:opacity-50 disabled:pointer-events-none active:translate-y-[1px] ${FOCUS_RING}`}
          >
            <svg className="w-4 h-4" viewBox="0 0 24 24" aria-hidden="true">
              <path
                fill="#4285F4"
                d="M23.745 12.27c0-.7-.06-1.4-.19-2.07H12v4.51h6.6c-.29 1.52-1.14 2.82-2.4 3.68v3.05h3.88c2.27-2.09 3.665-5.17 3.665-9.17z"
              />
              <path
                fill="#34A853"
                d="M12 24c3.24 0 5.95-1.08 7.93-2.91l-3.88-3.05c-1.08.72-2.45 1.16-4.05 1.16-3.12 0-5.77-2.1-6.72-4.93H1.28v3.15C3.26 21.3 7.31 24 12 24z"
              />
              <path
                fill="#FBBC05"
                d="M5.28 14.27c-.25-.72-.38-1.49-.38-2.27s.13-1.55.38-2.27V6.58H1.28C.46 8.21 0 10.05 0 12s.46 3.79 1.28 5.42l4-3.15z"
              />
              <path
                fill="#EA4335"
                d="M12 4.75c1.77 0 3.35.61 4.6 1.8l3.42-3.42C17.95 1.19 15.24 0 12 0 7.31 0 3.26 2.7 1.28 6.58l4 3.15c.95-2.83 3.6-4.98 6.72-4.98z"
              />
            </svg>
            <span>Continue with Google</span>
          </button>
        </motion.div>

        {/* Back Link */}
        <div className="text-center mt-6">
          <Link to="/" className="text-11 font-mono text-nt3 hover:text-nt transition-colors">
            ← Return to NorAI Homepage
          </Link>
        </div>
      </div>
    </div>
  )
}
