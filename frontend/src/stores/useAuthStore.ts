import { create } from 'zustand'

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
  logout: () => void
}

const STORAGE_KEY_TOKEN = 'norai_auth_token'
const STORAGE_KEY_USER = 'norai_auth_user'

const initialToken = typeof localStorage !== 'undefined' ? localStorage.getItem(STORAGE_KEY_TOKEN) : null
const initialUser = typeof localStorage !== 'undefined' ? JSON.parse(localStorage.getItem(STORAGE_KEY_USER) || 'null') : null

export const useAuthStore = create<AuthState>((set) => ({
  user: initialUser,
  token: initialToken,
  isAuthModalOpen: false,
  authModalTab: 'login',

  openAuthModal: (tab = 'login') => set({ isAuthModalOpen: true, authModalTab: tab }),
  closeAuthModal: () => set({ isAuthModalOpen: false }),

  setSession: (token, user) => {
    localStorage.setItem(STORAGE_KEY_TOKEN, token)
    localStorage.setItem(STORAGE_KEY_USER, JSON.stringify(user))
    set({ token, user, isAuthModalOpen: false })
  },

  logout: () => {
    localStorage.removeItem(STORAGE_KEY_TOKEN)
    localStorage.removeItem(STORAGE_KEY_USER)
    set({ token: null, user: null })
  },
}))
