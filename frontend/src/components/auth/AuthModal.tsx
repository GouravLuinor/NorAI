import React, { useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { X, Mail, Lock, User as UserIcon, ArrowRight, Sparkles } from 'lucide-react'
import { useAuthStore } from '../../stores/useAuthStore'

export function AuthModal() {
  const { isAuthModalOpen, authModalTab, closeAuthModal, setSession } = useAuthStore()
  const [tab, setTab] = useState<'login' | 'signup'>(authModalTab)
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [fullName, setFullName] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  if (!isAuthModalOpen) return null

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError('')
    setLoading(true)

    try {
      const mockToken = `token_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`
      const mockUser = {
        id: `usr_${Date.now()}`,
        email: email || 'user@example.com',
        fullName: tab === 'signup' ? fullName || email.split('@')[0] : email.split('@')[0],
        subscriptionTier: 'free' as const,
        monthlyQuotaMinutes: 15,
        usedMinutesThisMonth: 0,
      }

      setSession(mockToken, mockUser)
      closeAuthModal()
    } catch (err: any) {
      setError(err.message || 'Failed to authenticate. Please check your credentials.')
    } finally {
      setLoading(false)
    }
  }

  const handleGoogleAuth = () => {
    setLoading(true)
    const mockToken = `goog_token_${Date.now()}`
    const mockUser = {
      id: `goog_${Date.now()}`,
      email: 'student@university.edu',
      fullName: 'University Student',
      subscriptionTier: 'free' as const,
      monthlyQuotaMinutes: 15,
      usedMinutesThisMonth: 0,
    }
    setTimeout(() => {
      setSession(mockToken, mockUser)
      closeAuthModal()
      setLoading(false)
    }, 600)
  }

  const handleGuestTrial = () => {
    const mockToken = `guest_${Date.now()}`
    const mockUser = {
      id: `guest_${Date.now()}`,
      email: 'guest@trial.norai',
      fullName: 'Guest User (Free Trial)',
      isAnonymous: true,
      subscriptionTier: 'free' as const,
      monthlyQuotaMinutes: 15,
      usedMinutesThisMonth: 0,
    }
    setSession(mockToken, mockUser)
    closeAuthModal()
  }

  return (
    <AnimatePresence>
      <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-xs p-4">
        <motion.div
          initial={{ opacity: 0, scale: 0.95, y: 10 }}
          animate={{ opacity: 1, scale: 1, y: 0 }}
          exit={{ opacity: 0, scale: 0.95, y: 10 }}
          transition={{ duration: 0.2 }}
          className="relative w-full max-w-md overflow-hidden rounded-lg bg-nb border border-bdr p-6 shadow-bp"
        >
          {/* Close button */}
          <button
            onClick={closeAuthModal}
            className="absolute top-4 right-4 text-nt3 hover:text-nt p-1 rounded transition-colors"
          >
            <X size={18} />
          </button>

          {/* Header */}
          <div className="mb-6 text-center">
            <div className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full bg-npb text-npt font-mono text-10 font-medium mb-3">
              <Sparkles size={11} className="text-np" />
              <span>NorAI Study Platform</span>
            </div>
            <h2 className="text-22-bold font-serif text-nt">
              {tab === 'login' ? 'Welcome Back' : 'Create Your Account'}
            </h2>
            <p className="text-12-regular text-nt2 mt-1 font-sans">
              {tab === 'login' ? 'Sign in to access your saved lectures & tutor threads' : 'Turn lecture videos into study notes & AI tutor'}
            </p>
          </div>

          {/* Segmented Control */}
          <div className="grid grid-cols-2 p-1 bg-ns2 rounded mb-6 border border-bdr font-display text-11 uppercase font-semibold">
            <button
              onClick={() => setTab('login')}
              className={`py-1.5 rounded transition-all ${
                tab === 'login'
                  ? 'bg-ns text-np shadow-xs'
                  : 'text-nt3 hover:text-nt'
              }`}
            >
              Log In
            </button>
            <button
              onClick={() => setTab('signup')}
              className={`py-1.5 rounded transition-all ${
                tab === 'signup'
                  ? 'bg-ns text-np shadow-xs'
                  : 'text-nt3 hover:text-nt'
              }`}
            >
              Sign Up
            </button>
          </div>

          {/* Error Banner */}
          {error && (
            <div className="mb-4 p-3 rounded bg-nrb border border-nrbr text-nrt text-12-regular">
              {error}
            </div>
          )}

          {/* Form */}
          <form onSubmit={handleSubmit} className="space-y-4">
            {tab === 'signup' && (
              <div>
                <label className="block text-10-medium font-mono uppercase text-nt3 mb-1">Full Name</label>
                <div className="relative">
                  <UserIcon size={15} className="absolute left-3 top-1/2 -translate-y-1/2 text-nt3" />
                  <input
                    type="text"
                    required
                    value={fullName}
                    onChange={(e) => setFullName(e.target.value)}
                    placeholder="Alex Morgan"
                    className="w-full pl-9 pr-3 py-2 text-12-regular bg-ns border border-bdr rounded focus:border-np focus:outline-hidden transition-colors"
                  />
                </div>
              </div>
            )}

            <div>
              <label className="block text-10-medium font-mono uppercase text-nt3 mb-1">Email Address</label>
              <div className="relative">
                <Mail size={15} className="absolute left-3 top-1/2 -translate-y-1/2 text-nt3" />
                <input
                  type="email"
                  required
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  placeholder="alex@university.edu"
                  className="w-full pl-9 pr-3 py-2 text-12-regular bg-ns border border-bdr rounded focus:border-np focus:outline-hidden transition-colors"
                />
              </div>
            </div>

            <div>
              <label className="block text-10-medium font-mono uppercase text-nt3 mb-1">Password</label>
              <div className="relative">
                <Lock size={15} className="absolute left-3 top-1/2 -translate-y-1/2 text-nt3" />
                <input
                  type="password"
                  required
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="••••••••"
                  className="w-full pl-9 pr-3 py-2 text-12-regular bg-ns border border-bdr rounded focus:border-np focus:outline-hidden transition-colors"
                />
              </div>
            </div>

            <button
              type="submit"
              disabled={loading}
              className="w-full py-2.5 px-4 bg-np hover:bg-nph text-npfg font-display text-11 font-semibold uppercase tracking-wider rounded shadow-bp flex items-center justify-center gap-2 transition-colors disabled:opacity-50 cursor-pointer active:translate-y-0.5"
            >
              {loading ? (
                <span>Authenticating...</span>
              ) : (
                <>
                  <span>{tab === 'login' ? 'Sign In' : 'Create Free Account'}</span>
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
            <span className="relative px-3 bg-nb text-10-medium font-mono uppercase text-nt3">
              OR CONTINUE WITH
            </span>
          </div>

          {/* Social Auth & Guest */}
          <div className="space-y-2">
            <button
              onClick={handleGoogleAuth}
              disabled={loading}
              className="w-full py-2.5 px-4 bg-ns border border-bdr hover:bg-ns2 text-nt font-display text-11 font-medium uppercase tracking-wider rounded flex items-center justify-center gap-2 transition-colors cursor-pointer"
            >
              <svg className="w-4 h-4" viewBox="0 0 24 24">
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

            <button
              onClick={handleGuestTrial}
              className="w-full py-2 px-4 text-10-medium font-mono text-nt3 hover:text-nt transition-colors text-center cursor-pointer uppercase tracking-wider"
            >
              Continue as Guest (1 Video Free Trial)
            </button>
          </div>
        </motion.div>
      </div>
    </AnimatePresence>
  )
}
