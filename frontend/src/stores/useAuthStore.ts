import { create } from 'zustand'
import type { Session } from '@supabase/supabase-js'
import { supabase } from '../lib/supabaseClient'
import { apiFetch } from '../lib/http'
import { DEFAULT_TRIAL_QUOTA_MINUTES } from '../config/features'

export interface UserProfile {
  id: string
  email: string
  fullName?: string
  avatarUrl?: string
  isAnonymous?: boolean
  subscriptionTier?: 'free' | 'starter' | 'pro'
  monthlyQuotaMinutes?: number
  usedMinutesThisMonth?: number
}

export interface QuotaInfo {
  plan_tier: 'free' | 'starter' | 'pro'
  subscription_status: string
  monthly_minutes_quota: number
  used_minutes_this_month: number
  remaining_minutes: number
  is_anonymous: boolean
}

interface AuthState {
  user: UserProfile | null
  token: string | null
  quota: QuotaInfo | null
  isLoadingSession: boolean
  /** True while the session came from a password-reset email link. */
  isPasswordRecovery: boolean
  isAuthModalOpen: boolean
  authModalTab: 'login' | 'signup'
  openAuthModal: (tab?: 'login' | 'signup') => void
  closeAuthModal: () => void
  setSession: (token: string, user: UserProfile) => void
  logout: () => Promise<void>
  initAuth: () => Promise<void>
  clearPasswordRecovery: () => void
  refreshQuota: () => Promise<void>
}

const mapSession = (session: Session | null) => {
  if (!session?.user) return { token: null, user: null }
  const u = session.user
  return {
    token: session.access_token,
    user: {
      id: u.id,
      email: u.email ?? '',
      fullName: (u.user_metadata?.full_name as string) || (u.user_metadata?.name as string) || u.email?.split('@')[0],
      avatarUrl: u.user_metadata?.avatar_url as string | undefined,
      isAnonymous: u.is_anonymous ?? false,
      monthlyQuotaMinutes: DEFAULT_TRIAL_QUOTA_MINUTES,
    } as UserProfile,
  }
}

// One auth listener for the app's lifetime. initAuth() runs from an effect,
// which StrictMode invokes twice; each call used to add another listener, so
// every auth event fired its side effects (quota fetch, thread reloads) twice.
let _authSubscription: { unsubscribe: () => void } | null = null

export const useAuthStore = create<AuthState>((set, get) => ({
  user: null,
  token: null,
  quota: null,
  isLoadingSession: true,
  isPasswordRecovery: false,
  isAuthModalOpen: false,
  authModalTab: 'login',

  openAuthModal: (tab = 'login') => set({ isAuthModalOpen: true, authModalTab: tab }),
  closeAuthModal: () => set({ isAuthModalOpen: false }),

  setSession: (token, user) => set({ token, user, isAuthModalOpen: false }),

  refreshQuota: async () => {
    // Only query quota for authenticated users with active token
    if (!get().token) {
      set({ quota: null })
      return
    }
    try {
      const quota = await apiFetch<QuotaInfo>('/quota')
      if (!quota) {
        set({ quota: null })
        return
      }
      const current = get().user
      // Only create a new `user` object when subscription fields actually
      // changed. A fresh reference every call would re-trigger effects that
      // depend on `user` (e.g. BillingPage) -> infinite refetch loop.
      if (
        current &&
        (current.subscriptionTier !== quota.plan_tier ||
          current.monthlyQuotaMinutes !== quota.monthly_minutes_quota ||
          current.usedMinutesThisMonth !== quota.used_minutes_this_month)
      ) {
        set({
          quota,
          user: {
            ...current,
            subscriptionTier: quota.plan_tier,
            monthlyQuotaMinutes: quota.monthly_minutes_quota,
            usedMinutesThisMonth: quota.used_minutes_this_month,
          },
        })
      } else {
        set({ quota })
      }
    } catch {
      set({ quota: null })
    }
  },

  logout: async () => {
    try {
      await Promise.race([
        supabase.auth.signOut(),
        new Promise((resolve) => setTimeout(resolve, 1000)),
      ])
    } catch (e) {
      console.warn('Supabase signOut error/network unreachable:', e)
    } finally {
      // Thread state is reset by Sidebar's user-id effect; doing it here too
      // raced that effect and could wipe the freshly loaded threads.
      set({ token: null, user: null, quota: null, isPasswordRecovery: false })
    }
  },

  clearPasswordRecovery: () => set({ isPasswordRecovery: false }),

  initAuth: async () => {
    if (!_authSubscription) {
      const { data } = supabase.auth.onAuthStateChange((event, session) => {
        const next = mapSession(session)
        set({
          ...next,
          isLoadingSession: false,
          isAuthModalOpen: false,
          ...(event === 'PASSWORD_RECOVERY' ? { isPasswordRecovery: true } : {}),
          ...(event === 'SIGNED_OUT' ? { isPasswordRecovery: false } : {}),
        })
        if (next.token) {
          void get().refreshQuota()
        } else {
          set({ quota: null })
        }
      })
      _authSubscription = data.subscription
    }

    try {
      const { data } = await supabase.auth.getSession()
      const { token, user } = mapSession(data.session)
      set({ token, user, isLoadingSession: false })
      if (token) {
        await get().refreshQuota()
      }
    } catch {
      set({ token: null, user: null, quota: null, isLoadingSession: false })
    }
  },
}))
