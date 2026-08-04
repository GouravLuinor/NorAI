import { useState, useEffect } from 'react'
import { Sun, Moon } from 'lucide-react'

const STORAGE_KEY = 'norai-theme'

export function ThemeToggle() {
  const [theme, setTheme] = useState<'dark' | 'light'>(
    () => (localStorage.getItem(STORAGE_KEY) as 'dark' | 'light') || 'light'
  )

  useEffect(() => {
    document.documentElement.setAttribute('data-theme', theme)
    localStorage.setItem(STORAGE_KEY, theme)
    const meta = document.querySelector('meta[name="theme-color"]')
    if (meta) meta.setAttribute('content', theme === 'dark' ? '#0B1E3A' : '#F6F2E7')
  }, [theme])

  const toggle = () => setTheme((t) => (t === 'dark' ? 'light' : 'dark'))

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