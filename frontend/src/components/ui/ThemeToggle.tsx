import { useState, useEffect } from 'react'
import { Sun, Moon } from 'lucide-react'

const STORAGE_KEY = 'norai-theme'

export function ThemeToggle() {
  // No saved choice: follow the OS, so a student studying at night with a
  // dark system theme isn't greeted by a white page.
  const [theme, setTheme] = useState<'dark' | 'light'>(() => {
    const saved = localStorage.getItem(STORAGE_KEY) as 'dark' | 'light' | null
    if (saved) return saved
    return window.matchMedia?.('(prefers-color-scheme: dark)').matches ? 'dark' : 'light'
  })

  useEffect(() => {
    document.documentElement.setAttribute('data-theme', theme)
    const meta = document.querySelector('meta[name="theme-color"]')
    if (meta) meta.setAttribute('content', theme === 'dark' ? '#131614' : '#FBFBF8')
  }, [theme])

  // Saved only on an explicit toggle, so the OS default keeps following the OS.
  const toggle = () => {
    const next = theme === 'dark' ? 'light' : 'dark'
    try { localStorage.setItem(STORAGE_KEY, next) } catch { /* private mode */ }
    setTheme(next)
  }

  return (
    <button
      onClick={toggle}
      className="w-full py-1.5 rounded-md border border-bdr2 bg-transparent text-nt3 text-11 flex items-center justify-center gap-1.5 hover:bg-ns2 hover:text-nt2 hover:border-bdr2 transition active:translate-y-[1px] active:shadow-none"
      aria-label={`Switch to ${theme === 'dark' ? 'light' : 'dark'} mode`}
    >
      {theme === 'dark' ? <Sun size={13} strokeWidth={1.5} /> : <Moon size={13} strokeWidth={1.5} />}
      {theme === 'dark' ? 'Light' : 'Dark'} mode
    </button>
  )
}