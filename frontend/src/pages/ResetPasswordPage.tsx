import React, { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { Lock, ArrowRight } from 'lucide-react'
import { useAuthStore } from '../stores/useAuthStore'
import { useToastStore } from '../stores/useToastStore'
import { supabase } from '../lib/supabaseClient'
import { friendlyError } from '../lib/errorCopy'
import { FOCUS_RING } from '../components/ui/shared'
import { MIN_PASSWORD_LENGTH } from './AuthPage'

/**
 * Landing page for the Supabase password-reset email link. supabase-js reads
 * the recovery token from the URL, signs the user in, and emits
 * PASSWORD_RECOVERY; this page then lets them set a new password.
 */
export function ResetPasswordPage() {
  const navigate = useNavigate()
  const { token, isLoadingSession, clearPasswordRecovery } = useAuthStore()
  const addToast = useToastStore((s) => s.addToast)
  const [password, setPassword] = useState('')
  const [confirm, setConfirm] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError('')
    if (password.length < MIN_PASSWORD_LENGTH) {
      setError(`Use at least ${MIN_PASSWORD_LENGTH} characters for your password.`)
      return
    }
    if (password !== confirm) {
      setError('The two passwords do not match.')
      return
    }
    setLoading(true)
    try {
      const { error: updateError } = await supabase.auth.updateUser({ password })
      if (updateError) throw updateError
      clearPasswordRecovery()
      addToast('Password updated. You are signed in.', 'success')
      navigate('/app', { replace: true })
    } catch (err: unknown) {
      setError(friendlyError(err) || 'Could not update your password. Please try again.')
    } finally {
      setLoading(false)
    }
  }

  const inputClass = `w-full pl-9 pr-3 py-2.5 text-13 bg-ns border border-bdr rounded focus:border-np focus:outline-hidden transition-colors ${FOCUS_RING}`

  return (
    <div id="main" className="min-h-screen bg-nb text-nt font-sans flex flex-col justify-center py-12 px-4">
      <div className="mx-auto w-full max-w-md">
        <div className="text-center mb-6">
          <Link to="/" className="inline-block mb-4 font-serif font-black text-28 tracking-tight text-nt">
            Nor<span className="text-np">AI</span>
          </Link>
          <h1 className="text-24 font-bold font-serif text-nt">Choose a new password</h1>
        </div>

        <div className="bg-nb border border-bdr rounded-lg p-6 sm:p-8 shadow-bp">
          {isLoadingSession ? (
            <div className="flex items-center justify-center gap-2 text-12 text-nt3 py-6" role="status">
              <span className="h-3.5 w-3.5 rounded-full border-2 border-ns3 border-t-np animate-spin" />
              Verifying your reset link…
            </div>
          ) : !token ? (
            <div className="text-center space-y-4" role="alert">
              <p className="text-13 text-nt2">
                This reset link is invalid or has expired. Reset links work once and expire after an hour.
              </p>
              <Link
                to="/forgot-password"
                className={`inline-flex items-center gap-1.5 text-12 font-semibold text-np hover:underline rounded ${FOCUS_RING}`}
              >
                Send a new reset link <ArrowRight size={13} />
              </Link>
            </div>
          ) : (
            <form onSubmit={handleSubmit} className="space-y-4">
              {error && (
                <div className="p-3 rounded bg-nrb border border-nrbr text-nrt text-12" role="alert">
                  {error}
                </div>
              )}
              <div>
                <label htmlFor="new-password" className="block text-10 font-medium font-mono uppercase text-nt3 mb-1">
                  New password
                </label>
                <div className="relative">
                  <Lock size={15} className="absolute left-3 top-1/2 -translate-y-1/2 text-nt3" />
                  <input
                    id="new-password"
                    type="password"
                    required
                    minLength={MIN_PASSWORD_LENGTH}
                    autoComplete="new-password"
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    className={inputClass}
                  />
                </div>
                <p className="mt-1 text-11 text-nt3">At least {MIN_PASSWORD_LENGTH} characters.</p>
              </div>
              <div>
                <label htmlFor="confirm-password" className="block text-10 font-medium font-mono uppercase text-nt3 mb-1">
                  Confirm password
                </label>
                <div className="relative">
                  <Lock size={15} className="absolute left-3 top-1/2 -translate-y-1/2 text-nt3" />
                  <input
                    id="confirm-password"
                    type="password"
                    required
                    autoComplete="new-password"
                    value={confirm}
                    onChange={(e) => setConfirm(e.target.value)}
                    className={inputClass}
                  />
                </div>
              </div>
              <button
                type="submit"
                disabled={loading}
                className="w-full py-3 px-4 bg-np hover:bg-nph text-npfg font-display text-12 font-semibold uppercase tracking-wider rounded shadow-bp flex items-center justify-center gap-2 transition-colors disabled:opacity-50 disabled:pointer-events-none cursor-pointer"
              >
                {loading ? 'Saving…' : 'Update password'}
              </button>
            </form>
          )}
        </div>
      </div>
    </div>
  )
}
