import React, { useState, useEffect } from 'react'
import { Link, useNavigate, useLocation } from 'react-router-dom'
import { Mail, Lock, User as UserIcon, ArrowRight, ArrowLeft } from 'lucide-react'
import { Wordmark } from '../components/brand/Wordmark'
import { useAuthStore } from '../stores/useAuthStore'
import { supabase } from '../lib/supabaseClient'
import { friendlyError } from '../lib/errorCopy'
import { FOCUS_RING } from '../components/ui/shared'
import { FREE_MINUTES } from '../content/faq'
import { PAGE_META } from '../content/pages'
import { usePageMeta } from '../lib/usePageMeta'

type AuthMode = 'login' | 'signup' | 'forgot'

interface AuthPageProps {
  defaultMode?: AuthMode
}

export const MIN_PASSWORD_LENGTH = 8

export function AuthPage({ defaultMode = 'login' }: AuthPageProps) {
  const navigate = useNavigate()
  const location = useLocation()
  const { user, token } = useAuthStore()

  const [mode, setMode] = useState<AuthMode>(defaultMode)
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [fullName, setFullName] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [info, setInfo] = useState('')
  usePageMeta(mode === 'signup' ? PAGE_META.signup : { ...PAGE_META.login, path: mode === 'forgot' ? '/forgot-password' : '/login', noindex: mode === 'forgot' })

  // Determine redirect target
  const fromLoc = (location.state as { from?: { pathname: string; search?: string } })?.from
  const from = fromLoc?.pathname ? fromLoc.pathname + (fromLoc.search ?? '') : '/app'

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
      if (mode === 'forgot') {
        const { error: resetError } = await supabase.auth.resetPasswordForEmail(email, {
          redirectTo: `${window.location.origin}/reset-password`,
        })
        if (resetError) throw resetError
        // Same message whether or not the account exists (no email enumeration).
        setInfo('If an account exists for that email, a password reset link is on its way. Check your inbox and spam folder.')
      } else if (mode === 'signup') {
        if (password.length < MIN_PASSWORD_LENGTH) {
          throw new Error(`Use at least ${MIN_PASSWORD_LENGTH} characters for your password.`)
        }
        const { data, error: signUpError } = await supabase.auth.signUp({
          email,
          password,
          options: {
            data: { full_name: fullName || email.split('@')[0] },
            emailRedirectTo: `${window.location.origin}/app`,
          },
        })
        if (signUpError) throw signUpError
        if (!data.session) {
          // Supabase returns no session both for "confirm your email" and for an
          // already-registered address (deliberately indistinguishable).
          setInfo('Check your inbox for a confirmation link to activate your account. Already signed up with this email? Sign in or reset your password instead.')
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
    <div id="main" className="min-h-screen bg-nb text-nt font-sans flex flex-col justify-center py-12 px-4 sm:px-6">
      <div className="mx-auto w-full max-w-md">
        <div className="mb-7">
          <Link to="/" className={`inline-flex mb-8 rounded-sm ${FOCUS_RING}`} aria-label="NorAI home">
            <Wordmark size="md" />
          </Link>
          <h1 className="font-serif font-semibold text-32 leading-tight text-nt">
            {mode === 'login' ? 'Welcome back' : mode === 'signup' ? 'Create your free account' : 'Reset your password'}
          </h1>
          <p className="text-16 text-nt2 mt-2 leading-relaxed">
            {mode === 'login'
              ? 'Your lectures, notes, quizzes and tutor are where you left them.'
              : mode === 'signup'
                ? `${FREE_MINUTES} lecture-minutes a month, every feature included. No card.`
                : "Enter your account email and we'll send you a link to choose a new password."}
          </p>
        </div>

        {/* Form Container */}
        <div className="bg-ns border border-bdr rounded-lg p-6 sm:p-7 shadow-ev1">
          {/* Segmented Control */}
          {mode !== 'forgot' && (
          <div className="grid grid-cols-2 p-1 bg-ns2 rounded-md mb-6 text-14 font-bold">
            <button
              type="button"
              onClick={() => { setMode('login'); setError(''); setInfo('') }}
              className={`h-9 rounded-[4px] transition-colors cursor-pointer ${FOCUS_RING} ${
                mode === 'login'
                  ? 'bg-ns text-np shadow-ev1'
                  : 'text-nt3 hover:text-nt'
              }`}
            >
              Sign in
            </button>
            <button
              type="button"
              onClick={() => { setMode('signup'); setError(''); setInfo('') }}
              className={`h-9 rounded-[4px] transition-colors cursor-pointer ${FOCUS_RING} ${
                mode === 'signup'
                  ? 'bg-ns text-np shadow-ev1'
                  : 'text-nt3 hover:text-nt'
              }`}
            >
              Create account
            </button>
          </div>
          )}

          {/* Messages */}
          {error && (
            <div className="mb-4 p-3 rounded-md bg-nrb border border-nrbr text-nrt text-14" role="alert">
              {error}
            </div>
          )}
          {info && (
            <div className="mb-4 p-3 rounded-md bg-npb border border-npbr text-npt text-14" role="status">
              {info}
            </div>
          )}

          {/* Form */}
          <form onSubmit={handleSubmit} className="space-y-4">
            {mode === 'signup' && (
              <div>
                <label htmlFor="auth-name" className="block text-14 font-bold text-nt2 mb-1.5">
                  Name
                </label>
                <div className="relative">
                  <UserIcon size={16} className="absolute left-3.5 top-1/2 -translate-y-1/2 text-nt3" />
                  <input
                    id="auth-name"
                    type="text"
                    required
                    value={fullName}
                    onChange={(e) => setFullName(e.target.value)}
                    placeholder="Alex Morgan"
                    className={`w-full pl-10 pr-3 h-11 text-15 bg-ns border border-bdr2 rounded-md placeholder:text-nt4 focus:border-np focus:outline-hidden transition-colors ${FOCUS_RING}`}
                  />
                </div>
              </div>
            )}

            <div>
              <label htmlFor="auth-email-input" className="block text-14 font-bold text-nt2 mb-1.5">
                Email
              </label>
              <div className="relative">
                <Mail size={16} className="absolute left-3.5 top-1/2 -translate-y-1/2 text-nt3" />
                <input
                  id="auth-email-input"
                  type="email"
                  required
                  autoComplete="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  placeholder="alex@university.edu"
                  className={`w-full pl-10 pr-3 h-11 text-15 bg-ns border border-bdr2 rounded-md placeholder:text-nt4 focus:border-np focus:outline-hidden transition-colors ${FOCUS_RING}`}
                />
              </div>
            </div>

            {mode !== 'forgot' && (
            <div>
              <div className="flex items-baseline justify-between mb-1.5">
                <label htmlFor="auth-password-input" className="block text-14 font-bold text-nt2">
                  Password
                </label>
                {mode === 'login' && (
                  <button
                    type="button"
                    onClick={() => { setMode('forgot'); setError(''); setInfo('') }}
                    className={`text-14 font-bold text-np hover:underline cursor-pointer rounded ${FOCUS_RING}`}
                  >
                    Forgot password?
                  </button>
                )}
              </div>
              <div className="relative">
                <Lock size={16} className="absolute left-3.5 top-1/2 -translate-y-1/2 text-nt3" />
                <input
                  id="auth-password-input"
                  type="password"
                  required
                  minLength={mode === 'signup' ? MIN_PASSWORD_LENGTH : undefined}
                  autoComplete={mode === 'signup' ? 'new-password' : 'current-password'}
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="••••••••"
                  aria-describedby={mode === 'signup' ? 'auth-password-hint' : undefined}
                  className={`w-full pl-10 pr-3 h-11 text-15 bg-ns border border-bdr2 rounded-md placeholder:text-nt4 focus:border-np focus:outline-hidden transition-colors ${FOCUS_RING}`}
                />
              </div>
              {mode === 'signup' && (
                <p id="auth-password-hint" className="mt-1.5 text-13 text-nt3">
                  At least {MIN_PASSWORD_LENGTH} characters.
                </p>
              )}
            </div>
            )}

            <button
              type="submit"
              disabled={loading}
              className="w-full h-12 px-4 bg-npf hover:bg-npfh text-npfg text-16 font-bold rounded-md flex items-center justify-center gap-2 transition-colors disabled:opacity-50 disabled:pointer-events-none cursor-pointer active:translate-y-[1px]"
            >
              {loading ? (
                <span>{mode === 'forgot' ? 'Sending…' : mode === 'signup' ? 'Creating account…' : 'Signing in…'}</span>
              ) : (
                <>
                  <span>{mode === 'login' ? 'Sign in' : mode === 'signup' ? 'Create free account' : 'Send reset link'}</span>
                  <ArrowRight size={15} />
                </>
              )}
            </button>
          </form>

          {mode === 'forgot' ? (
            <div className="mt-5 text-center">
              <button
                type="button"
                onClick={() => { setMode('login'); setError(''); setInfo('') }}
                className={`inline-flex items-center gap-1.5 text-14 font-bold text-np hover:underline cursor-pointer rounded ${FOCUS_RING}`}
              >
                <ArrowLeft size={15} aria-hidden="true" /> Back to sign in
              </button>
            </div>
          ) : (
          <>
          {/* Divider */}
          <div className="relative my-6 text-center">
            <div className="absolute inset-0 flex items-center">
              <div className="w-full border-t border-bdr"></div>
            </div>
            <span className="relative px-3 bg-ns text-14 text-nt3">
              or
            </span>
          </div>

          {/* Google SSO */}
          <button
            onClick={handleGoogleAuth}
            disabled={loading}
            className={`w-full h-11 px-4 bg-ns border border-bdr2 hover:bg-ns2 text-nt text-15 font-bold rounded-md flex items-center justify-center gap-2 transition-colors cursor-pointer disabled:opacity-50 disabled:pointer-events-none active:translate-y-[1px] ${FOCUS_RING}`}
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
          </>
          )}
        </div>

        {/* Back Link */}
        <div className="text-center mt-6">
          <Link to="/" className={`inline-flex items-center gap-1.5 text-14 text-nt3 hover:text-nt transition-colors rounded-sm ${FOCUS_RING}`}>
            <ArrowLeft size={15} aria-hidden="true" /> Back to the NorAI home page
          </Link>
        </div>
      </div>
    </div>
  )
}
