import { motion, AnimatePresence } from 'framer-motion'
import { AlertTriangle, Clock } from 'lucide-react'
import { useRateLimitStore } from '../../stores/useRateLimitStore'

function formatCountdown(totalSeconds: number): string {
  if (totalSeconds <= 0) return '00h 00m 00s'
  const hours = Math.floor(totalSeconds / 3600)
  const minutes = Math.floor((totalSeconds % 3600) / 60)
  const seconds = totalSeconds % 60
  const pad = (n: number) => n.toString().padStart(2, '0')
  return `${pad(hours)}h ${pad(minutes)}m ${pad(seconds)}s`
}

export function RateLimitBanner() {
  const { isDailyLimited, remainingSeconds } = useRateLimitStore()

  if (!isDailyLimited) return null

  return (
    <AnimatePresence>
      <motion.aside
        initial={{ height: 0, opacity: 0 }}
        animate={{ height: 'auto', opacity: 1 }}
        exit={{ height: 0, opacity: 0 }}
        transition={{ duration: 0.25 }}
        aria-label="Service capacity notice"
        className="relative z-50 border-b border-amber-500/40 bg-amber-950/70 backdrop-blur-md text-amber-100 text-xs px-4 py-2.5 shadow-md overflow-hidden"
      >
        <div className="max-w-7xl mx-auto flex flex-col md:flex-row items-center justify-between gap-2.5">
          <div className="flex items-center gap-2.5 text-center md:text-left">
            <div className="flex-shrink-0 w-6 h-6 rounded-full bg-amber-500/20 border border-amber-500/40 flex items-center justify-center text-amber-400">
              <AlertTriangle size={13} />
            </div>
            <div>
              <span className="font-semibold text-amber-300">
                Google AI Studio Daily Quota Reached (500 RPD):
              </span>{' '}
              <span className="text-amber-200/90 font-sans">
                Processing new lectures is paused until daily quota renewal. Generated notes, mindmaps, and assessments remain fully accessible.
              </span>
            </div>
          </div>

          <div className="flex-shrink-0 flex items-center gap-2 bg-amber-900/60 border border-amber-600/40 px-3 py-1 rounded-full font-mono text-11 text-amber-300">
            <Clock size={12} className="animate-pulse text-amber-400" />
            <span>Pacific Midnight Reset:</span>
            <span className="font-bold tracking-wider text-amber-200">
              {formatCountdown(remainingSeconds)}
            </span>
          </div>
        </div>
      </motion.aside>
    </AnimatePresence>
  )
}
