import React, { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { X, Mail, Lock, User as UserIcon, ArrowRight } from 'lucide-react'
import { useAuthStore } from '../../stores/useAuthStore'
import { FREE_MINUTES } from '../../content/faq'
import { supabase } from '../../lib/supabaseClient'
import { friendlyError } from '../../lib/errorCopy'
import { Dialog } from '../ui/Dialog'
import { FOCUS_RING } from '../ui/shared'
import { MIN_PASSWORD_LENGTH } from '../../pages/AuthPage'

interface AuthModalProps {
  onSuccess?: () => void
}

export function AuthModal({ onSuccess }: AuthModalProps) {
  const { isAuthModalOpen, authModalTab, closeAuthModal } = useAuthStore()
  const navigate = useNavigate()
  const [tab, setTab] = useState<'login' | 'signup'>(authModalTab)
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [fullName, setFullName] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [info, setInfo] = useState('')

  useEffect(() => {
    setTab(authModalTab)
  }, [authModalTab])

  if (!isAuthModalOpen) return null

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError('')
    setInfo('')
    setLoading(true)

    try {
      if (tab === 'signup') {
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
          setInfo('Check your inbox for a confirmation link to activate your account. Already signed up with this email? Sign in or reset your password instead.')
        } else {
          closeAuthModal()
          onSuccess?.()
        }
      } else {
        const { error: signInError } = await supabase.auth.signInWithPassword({ email, password })
        if (signInError) throw signInError
        closeAuthModal()
        onSuccess?.()
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
        options: { redirectTo: window.location.origin },
      })
      if (oAuthError) throw oAuthError
    } catch (err: unknown) {
      setError(friendlyError(err) || 'Google sign-in is not configured yet.')
      setLoading(false)
    }
  }

  return (
    <Dialog ariaLabel={tab === 'login' ? 'Sign in to NorAI' : 'Create your NorAI account'} onClose={closeAuthModal}>
      <div className="relative w-full max-w-md overflow-hidden rounded-lg bg-ns border border-bdr p-6 sm:p-7 shadow-ev3">
        {/* Close button */}
        <button
          onClick={closeAuthModal}
          aria-label="Close sign-in dialog"
          className={`absolute top-4 right-4 text-nt3 hover:text-nt hover:bg-ns2 p-1.5 rounded-md transition-colors ${FOCUS_RING}`}
        >
          <X size={18} />
        </button>

        {/* Header */}
        <div className="mb-6 pr-8">
          <h2 className="text-24 font-semibold font-serif text-nt">
            {tab === 'login' ? 'Welcome back' : 'Create your free account'}
          </h2>
          <p className="text-15 text-nt2 mt-1.5 leading-relaxed">
            {tab === 'login'
              ? 'Your lectures, notes and tutor threads are waiting.'
              : `Free: ${FREE_MINUTES} lecture-minutes a month, every feature included. No card.`}
          </p>
        </div>

        {/* Segmented Control */}
        <div className="grid grid-cols-2 p-1 bg-ns2 rounded-md mb-6 text-14 font-bold">
          <button
            onClick={() => setTab('login')}
            className={`h-9 rounded-[4px] transition-colors cursor-pointer ${FOCUS_RING} ${
              tab === 'login'
                ? 'bg-ns text-np shadow-ev1'
                : 'text-nt3 hover:text-nt'
            }`}
          >
            Sign in
          </button>
          <button
            onClick={() => setTab('signup')}
            className={`h-9 rounded-[4px] transition-colors cursor-pointer ${FOCUS_RING} ${
              tab === 'signup'
                ? 'bg-ns text-np shadow-ev1'
                : 'text-nt3 hover:text-nt'
            }`}
          >
            Create account
          </button>
        </div>

        {/* Error Banner */}
        {error && (
          <div className="mb-4 p-3 rounded-md bg-nrb border border-nrbr text-nrt text-14" role="alert">
            {error}
          </div>
        )}

        {/* Info Banner */}
        {info && (
          <div className="mb-4 p-3 rounded-md bg-npb border border-npbr text-npt text-14" role="status">
            {info}
          </div>
        )}

        {/* Form */}
        <form onSubmit={handleSubmit} className="space-y-4">
          {tab === 'signup' && (
            <div>
              <label htmlFor="auth-fullname" className="block text-14 font-bold text-nt2 mb-1.5">Name</label>
              <div className="relative">
                <UserIcon size={16} className="absolute left-3.5 top-1/2 -translate-y-1/2 text-nt3" />
                <input
                  id="auth-fullname"
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
            <label htmlFor="auth-email" className="block text-14 font-bold text-nt2 mb-1.5">Email</label>
            <div className="relative">
              <Mail size={16} className="absolute left-3.5 top-1/2 -translate-y-1/2 text-nt3" />
              <input
                id="auth-email"
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

          <div>
            <div className="flex items-baseline justify-between mb-1.5">
              <label htmlFor="auth-password" className="block text-14 font-bold text-nt2">Password</label>
              {tab === 'login' && (
                <button
                  type="button"
                  onClick={() => { closeAuthModal(); navigate('/forgot-password') }}
                  className={`text-14 font-bold text-np hover:underline cursor-pointer rounded ${FOCUS_RING}`}
                >
                  Forgot password?
                </button>
              )}
            </div>
            <div className="relative">
              <Lock size={16} className="absolute left-3.5 top-1/2 -translate-y-1/2 text-nt3" />
              <input
                id="auth-password"
                type="password"
                required
                minLength={tab === 'signup' ? MIN_PASSWORD_LENGTH : undefined}
                autoComplete={tab === 'signup' ? 'new-password' : 'current-password'}
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="••••••••"
                className={`w-full pl-10 pr-3 h-11 text-15 bg-ns border border-bdr2 rounded-md placeholder:text-nt4 focus:border-np focus:outline-hidden transition-colors ${FOCUS_RING}`}
              />
            </div>
          </div>

          <button
            type="submit"
            disabled={loading}
            className="w-full h-12 px-4 bg-npf hover:bg-npfh text-npfg text-16 font-bold rounded-md flex items-center justify-center gap-2 transition-colors disabled:opacity-50 disabled:pointer-events-none cursor-pointer active:translate-y-[1px]"
          >
            {loading ? (
              <span>{tab === 'login' ? 'Signing in…' : 'Creating account…'}</span>
            ) : (
              <>
                <span>{tab === 'login' ? 'Sign in' : 'Create free account'}</span>
                <ArrowRight size={15} />
              </>
            )}
          </button>
        </form>

        {/* Divider */}
        <div className="relative my-5 text-center">
          <div className="absolute inset-0 flex items-center">
            <div className="w-full border-t border-bdr"></div>
          </div>
          <span className="relative px-3 bg-ns text-14 text-nt3">
            or
          </span>
        </div>

        {/* Social Auth */}
        <div className="space-y-2">
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
        </div>
      </div>
    </Dialog>
  )
}
