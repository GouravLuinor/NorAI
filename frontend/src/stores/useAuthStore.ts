import { create } from 'zustand'
import type { Session } from '@supabase/supabase-js'
import { supabase } from '../lib/supabaseClient'
import { apiFetch } from '../lib/http'

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
  isAuthModalOpen: boolean
  authModalTab: 'login' | 'signup'
  openAuthModal: (tab?: 'login' | 'signup') => void
  closeAuthModal: () => void
  setSession: (token: string, user: UserProfile) => void
  logout: () => Promise<void>
  initAuth: () => Promise<void>
  refreshQuota: () => Promise<void>
}

const mapSession = (session: Session | null) => {
  if (!session?.user) return { token: null, user: null }
  const u = session.user
  return {
    token: session.access_token,
    user: {
      id: u.id,
      email: u.email ?? `${u.id}@anonymous.norai`,
      fullName: (u.user_metadata?.full_name as string) || (u.user_metadata?.name as string) || u.email?.split('@')[0],
      avatarUrl: u.user_metadata?.avatar_url as string | undefined,
      isAnonymous: u.is_anonymous ?? false,
    } as UserProfile,
  }
}

export const useAuthStore = create<AuthState>((set, get) => ({
  user: null,
  token: null,
  quota: null,
  isAuthModalOpen: false,
  authModalTab: 'login',

  openAuthModal: (tab = 'login') => set({ isAuthModalOpen: true, authModalTab: tab }),
  closeAuthModal: () => set({ isAuthModalOpen: false }),

  setSession: (token, user) => set({ token, user, isAuthModalOpen: false }),

  refreshQuota: async () => {
    const { token } = get()
    if (!token) {
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
    await supabase.auth.signOut()
    set({ token: null, user: null, quota: null })
  },

  initAuth: async () => {
    const { data } = await supabase.auth.getSession()
    const { token, user } = mapSession(data.session)
    set({ token, user })

    supabase.auth.onAuthStateChange((_event, session) => {
      const next = mapSession(session)
      set({ ...next, isAuthModalOpen: false })
      if (next.token) {
        void get().refreshQuota()
      } else {
        set({ quota: null })
      }
    })

    if (token) {
      await get().refreshQuota()
    }
  },
}))
