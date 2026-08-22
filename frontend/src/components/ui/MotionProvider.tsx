import type { ReactNode } from 'react'
import { MotionConfig } from 'framer-motion'

// P3.4: the global MotionConfig lives in its own lazy module so the
// framer-motion runtime (~40KB gz) is fetched as an async chunk after
// hydration instead of being bundled into the shared entry chunk that every
// route — including marketing pages — pays for.
export function MotionProvider({ children }: { children: ReactNode }) {
  return <MotionConfig reducedMotion="user">{children}</MotionConfig>
}
