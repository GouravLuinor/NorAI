import { create } from 'zustand'
import type { Session } from '@supabase/supabase-js'
import { supabase } from '../lib/supabaseClient'

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

interface AuthState {
  user: UserProfile | null
  token: string | null
  isAuthModalOpen: boolean
  authModalTab: 'login' | 'signup'
  openAuthModal: (tab?: 'login' | 'signup') => void
  closeAuthModal: () => void
  setSession: (token: string, user: UserProfile) => void
  logout: () => Promise<void>
  initAuth: () => Promise<void>
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

export const useAuthStore = create<AuthState>((set) => ({
  user: null,
  token: null,
  isAuthModalOpen: false,
  authModalTab: 'login',

  openAuthModal: (tab = 'login') => set({ isAuthModalOpen: true, authModalTab: tab }),
  closeAuthModal: () => set({ isAuthModalOpen: false }),

  setSession: (token, user) => set({ token, user, isAuthModalOpen: false }),

  logout: async () => {
    await supabase.auth.signOut()
    set({ token: null, user: null })
  },

  initAuth: async () => {
    const { data } = await supabase.auth.getSession()
    const { token, user } = mapSession(data.session)
    set({ token, user })

    supabase.auth.onAuthStateChange((_event, session) => {
      const next = mapSession(session)
      set({ ...next, isAuthModalOpen: false })
    })
  },
}))
