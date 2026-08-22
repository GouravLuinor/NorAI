import { useEffect, useRef } from 'react'

// P4.5: tier0 NumberTicker — spring-less odometer that writes textContent
// directly (zero React re-renders during the count-up), tabular-nums by
// contract, and instant under prefers-reduced-motion. `format` lets callers
// keep their currency/compact formatting.
export function NumberTicker({
  value,
  format = (v: number) => String(Math.round(v)),
  duration = 600,
}: {
  value: number
  format?: (v: number) => string
  duration?: number
}) {
  const ref = useRef<HTMLSpanElement>(null)
  const fromRef = useRef(0)

  useEffect(() => {
    const el = ref.current
    if (!el) return

    const reduced =
      typeof window !== 'undefined' &&
      window.matchMedia?.('(prefers-reduced-motion: reduce)').matches
    if (reduced) {
      el.textContent = format(value)
      fromRef.current = value
      return
    }

    const from = fromRef.current
    const delta = value - from
    if (delta === 0) {
      el.textContent = format(value)
      return
    }

    let raf = 0
    const start = performance.now()
    const tick = (now: number) => {
      // expo-out: fast start, gentle settle — matches --ease-out-expo feel.
      const t = Math.min(1, (now - start) / duration)
      const eased = t === 1 ? 1 : 1 - Math.pow(2, -10 * t)
      el.textContent = format(from + delta * eased)
      if (t < 1) raf = requestAnimationFrame(tick)
      else fromRef.current = value
    }
    raf = requestAnimationFrame(tick)
    return () => cancelAnimationFrame(raf)
    // Re-run only when the numeric target changes.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [value])

  return (
    <span ref={ref} className="tabular-nums">
      {format(value)}
    </span>
  )
}
