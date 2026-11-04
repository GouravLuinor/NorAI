import { ArrowDown, BookOpen, HardDrive } from 'lucide-react'
import { Wordmark } from './Wordmark'
import { FOCUS_RING } from '../ui/shared'

/**
 * The intro band on a local install (NORAI_MODE=local), where the marketing
 * landing page is skipped and /app is the front door. It is the stack signage
 * from the product's own world: green rail ground, a Literata headline, and a
 * shelf of spines. The six lettered spines are the six things one lecture
 * becomes, in the colour of the study mode that opens them.
 */

interface Spine {
  /** Lettering, only on the six study-mode spines. */
  label?: string
  w: number
  h: number
  bg: string
  fg?: string
  /** Brass band across the spine, as on a library binding. */
  band?: number
}

// Decoration spines are tints of the rail so the lettered ones carry the colour.
const T = (pct: number) => `color-mix(in srgb, var(--color-rail-ink) ${pct}%, var(--color-rail-deep))`

const SPINES: Spine[] = [
  { w: 22, h: 64, bg: T(14), band: 14 },
  { w: 30, h: 82, bg: T(9) },
  { w: 18, h: 58, bg: T(20), band: 40 },
  { w: 26, h: 76, bg: T(12) },
  { w: 20, h: 70, bg: T(7), band: 22 },
  { w: 34, h: 108, bg: '#EAF1EC', fg: '#1F4D3F', label: 'Notes' },
  { w: 24, h: 84, bg: T(16) },
  { w: 34, h: 124, bg: '#2F6FB2', fg: '#FFFFFF', label: 'Revision' },
  { w: 20, h: 66, bg: T(10), band: 30 },
  { w: 34, h: 100, bg: '#B8432F', fg: '#FFFFFF', label: 'Quiz' },
  { w: 28, h: 78, bg: T(18) },
  { w: 34, h: 116, bg: '#6B4FA0', fg: '#FFFFFF', label: 'Cards' },
  { w: 18, h: 62, bg: T(8), band: 18 },
  { w: 34, h: 96, bg: '#C8932E', fg: '#16181A', label: 'Map' },
  { w: 24, h: 88, bg: T(13) },
  { w: 34, h: 112, bg: '#F6EBD2', fg: '#8A5F12', label: 'Tutor' },
  { w: 22, h: 72, bg: T(11), band: 52 },
  { w: 30, h: 60, bg: T(17) },
  { w: 18, h: 80, bg: T(9) },
  { w: 26, h: 66, bg: T(15), band: 26 },
  { w: 20, h: 54, bg: T(7) },
]

// Plain spines continue the row outward so the shelf spans the whole band, however wide.
const FILLER = SPINES.filter((s) => !s.label)
const SIDE = 11
const ROW: Spine[] = [
  ...Array.from({ length: SIDE }, (_, i) => FILLER[(i * 5 + 3) % FILLER.length]),
  ...SPINES,
  ...Array.from({ length: SIDE }, (_, i) => FILLER[(i * 7 + 1) % FILLER.length]),
]
const CENTER = Math.floor(ROW.length / 2)
const SCALE = 1.3

function smoothScrollTo(selector: string, focusSelector?: string) {
  const el = document.querySelector<HTMLElement>(selector)
  if (!el) return
  const reduce = window.matchMedia('(prefers-reduced-motion: reduce)').matches
  el.scrollIntoView({ behavior: reduce ? 'auto' : 'smooth', block: 'start' })
  if (focusSelector) {
    // Wait for the scroll to land so the focus doesn't yank the page mid-glide.
    window.setTimeout(() => document.querySelector<HTMLElement>(focusSelector)?.focus({ preventScroll: true }), reduce ? 0 : 450)
  }
}

export function LocalHero() {
  return (
    <header className="rail local-hero w-full relative overflow-hidden">
      <div className="mx-auto max-w-3xl px-4 sm:px-6 pt-4">
        <div className="flex items-center justify-between gap-3">
          <Wordmark size="md" />
          <span className="inline-flex items-center gap-1.5 rounded-full border border-bdr2 px-2.5 py-1 text-12 font-bold text-nt2">
            <HardDrive size={13} strokeWidth={1.75} aria-hidden="true" />
            Running on this PC. No account.
          </span>
        </div>

        <div className="pt-12 sm:pt-16 pb-9 sm:pb-12">
          <h1 className="local-hero-rise font-serif font-semibold text-nt text-balance text-[clamp(2.125rem,5.4vw,3.5rem)] leading-[1.06] tracking-[-0.015em] max-w-[22ch]">
            Turn a lecture into something you can revise.
          </h1>
          <p className="local-hero-rise mt-5 max-w-[52ch] text-17 leading-relaxed text-nt2" style={{ animationDelay: '90ms' }}>
            Paste a YouTube link or drop in a recording, PDF or slide deck. You get chapter notes, a revision
            sheet, a quiz, flashcards and a tutor that answers only from your lecture.
          </p>
          <div className="local-hero-rise mt-7 flex flex-wrap items-center gap-3" style={{ animationDelay: '170ms' }}>
            <button
              type="button"
              onClick={() => smoothScrollTo('#add-heading', '#lecture-url')}
              className={`inline-flex items-center gap-2 h-12 px-6 rounded-md bg-npf text-npfg text-16 font-bold shadow-ev2 hover:bg-npfh transition-colors cursor-pointer ${FOCUS_RING}`}
            >
              Add a lecture
              <ArrowDown size={16} strokeWidth={2.25} aria-hidden="true" />
            </button>
            <button
              type="button"
              onClick={() => smoothScrollTo('#demo-heading')}
              className={`inline-flex items-center gap-2 h-12 px-5 rounded-md border-[1.5px] border-bdr2 text-nt text-16 font-bold hover:bg-ns2 transition-colors cursor-pointer ${FOCUS_RING}`}
            >
              <BookOpen size={16} strokeWidth={1.75} aria-hidden="true" />
              Open a demo
            </button>
          </div>
        </div>
      </div>

      {/* The shelf. Decorative; the same six outputs are listed for screen readers. */}
      <ul className="sr-only">
        {SPINES.filter((s) => s.label).map((s) => <li key={s.label}>{s.label}</li>)}
      </ul>
      <div className="local-hero-shelf" aria-hidden="true">
        <div className="flex items-end justify-center gap-[3px] px-2">
          {ROW.map((s, i) => (
            <div
              key={i}
              className="local-hero-spine relative shrink-0 rounded-t-[3px] overflow-hidden"
              style={{
                width: s.w * SCALE,
                height: s.h * SCALE,
                background: s.bg,
                color: s.fg,
                animationDelay: `${240 + Math.abs(i - CENTER) * 46}ms`,
              }}
            >
              {s.band != null && (
                <span className="absolute inset-x-0 h-[3px] bg-brass/80" style={{ top: `${s.band}%` }} />
              )}
              {s.label && (
                <span
                  className="absolute inset-0 flex items-center justify-center text-13 font-bold uppercase tracking-[0.08em]"
                  style={{ writingMode: 'vertical-rl' }}
                >
                  {s.label}
                </span>
              )}
            </div>
          ))}
        </div>
        <div className="local-hero-board" />
      </div>
    </header>
  )
}
