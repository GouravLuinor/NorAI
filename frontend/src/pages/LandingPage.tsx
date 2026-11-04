import { useState, type ReactNode } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { ArrowRight, ArrowUpRight, LogOut, Menu, X } from 'lucide-react'
import { useAuthStore } from '../stores/useAuthStore'
import { useAppConfigStore } from '../stores/useAppConfigStore'
import { FOCUS_RING, LINK_RING } from '../components/ui/shared'
import { DEMO_LECTURES_CONFIG, PRIMARY_DEMO_LECTURE_ID } from '../config/features'
import { FaqList } from '../components/marketing/FaqList'
import { FREE_MINUTES, HOME_FAQ } from '../content/faq'
import { PAGE_META } from '../content/pages'
import { usePageMeta } from '../lib/usePageMeta'
import { Wordmark } from '../components/brand/Wordmark'
import { ShelfMark } from '../components/ui/ShelfMark'

interface LandingPageProps {
  onStartWorkspace: () => void
}

/** What one processed lecture contains. Each output wears its zone colour,
 *  the same one it has in the workspace. */
const OUTPUTS = [
  {
    name: 'Study notes',
    zone: 'bg-z-notes',
    body: 'Chapter-wise notes in the order your professor taught, with formulas typeset properly and the slides that mattered pulled out of the video.',
  },
  {
    name: 'Revision sheet',
    zone: 'bg-z-revision',
    body: 'The night-before version: key takeaways and definitions per chapter, short enough to read on the bus.',
  },
  {
    name: 'Quiz',
    zone: 'bg-z-quiz',
    body: 'Multiple-choice and true/false questions at three levels, each linked back to the notes so you can see why an answer is right.',
  },
  {
    name: 'Flashcards',
    zone: 'bg-z-cards',
    body: 'A deck for every lecture. Rate each card and spaced repetition brings back the ones you keep missing.',
  },
  {
    name: 'Tutor',
    zone: 'bg-brass',
    body: 'Ask in plain words. Nora answers only from your lecture and shows the moment in the video it is quoting.',
  },
  {
    name: 'Mind map',
    zone: 'bg-brass',
    body: 'Each chapter as a concept tree, for when you need to see how the topics connect before an exam.',
  },
] as const

const STEPS = [
  {
    title: 'Upload the recording, PDF or slides',
    body: 'A video (MP4, MOV, MKV, AVI, WebM), a PDF, Word file or slide deck, or a Google Drive or web link. A recorded class, a university lecture, an online course, a textbook chapter: anything you need to learn from.',
  },
  {
    title: 'Check the estimate, then let it run',
    body: 'You see how many minutes it will use before anything starts. Close the tab if you like; it keeps working and can notify you.',
  },
  {
    title: 'Study from it',
    body: 'Notes, revision sheet, quiz, flashcards and the tutor open together in one workspace, and stay in your library.',
  },
] as const

/** The primary demo lecture's real chapter ranges (from its video map). */
const DEMO_RANGES = [
  { ch: '01', at: '0:12', title: 'Course Introduction and Goals' },
  { ch: '02', at: '3:04', title: 'Defining Computational Problems' },
  { ch: '03', at: '6:32', title: 'Generalizing Problems and Algorithms' },
  { ch: '04', at: '10:57', title: 'Example: The Birthday Problem' },
] as const

const DEMO_CODES: Record<string, string> = {
  'Computer Science & Algorithms': 'CS',
  'Mathematics & Calculus': 'MATH',
  'Physics & Mechanics': 'PHYS',
  'Economics & Finance': 'ECON',
  'History & Humanities': 'HIST',
}

const DEMO_SLUGS: Record<string, string> = {
  '8821152f-f6de-49e9-a885-0adaac6ba4cb': 'algorithms-and-computation',
  '01b04840-fddb-4b31-a211-7bb28f189621': 'calculus-differentiation',
  'c8cab2e7-52b7-4cdc-8386-f440d02f3f45': 'newtonian-mechanics',
  '2e983ee0-ae41-4910-9239-099b34dee04c': 'financial-markets',
  '5f7225bf-ba41-46b9-aea9-da91c032b515': 'civil-war-reconstruction',
}

function Container({ children, className = '' }: { children: ReactNode; className?: string }) {
  return <div className={`mx-auto w-full max-w-6xl px-4 sm:px-6 ${className}`}>{children}</div>
}

const PRIMARY_BTN = `inline-flex items-center justify-center gap-2 rounded-md bg-npf px-6 h-12 text-16 font-bold text-npfg hover:bg-npfh active:translate-y-px cursor-pointer transition-colors ${FOCUS_RING}`

export function LandingPage({ onStartWorkspace }: LandingPageProps) {
  const navigate = useNavigate()
  const user = useAuthStore((s) => s.user)
  const logout = useAuthStore((s) => s.logout)
  const [menuOpen, setMenuOpen] = useState(false)

  usePageMeta(PAGE_META.home)

  const start = () => (user ? onStartWorkspace() : navigate('/signup'))
  const signOut = async () => {
    setMenuOpen(false)
    await logout()
    navigate('/')
  }

  const navLinks = (
    <>
      <a href="#how-it-works" className={`hover:text-nt transition-colors ${LINK_RING}`} onClick={() => setMenuOpen(false)}>How it works</a>
      <a href="#demo" className={`hover:text-nt transition-colors ${LINK_RING}`} onClick={() => setMenuOpen(false)}>Demo lectures</a>
      <Link to="/pricing" className={`hover:text-nt transition-colors ${LINK_RING}`}>It's free</Link>
      <a href="#faq" className={`hover:text-nt transition-colors ${LINK_RING}`} onClick={() => setMenuOpen(false)}>FAQ</a>
    </>
  )

  // Hosted installs have YouTube switched off (servers get blocked), so the
  // hero pitches upload; the paste-a-link box only shows where it can work.
  const youtubeOn = useAppConfigStore((s) => s.sources.includes('youtube'))
  const [pasteUrl, setPasteUrl] = useState('')
  const [isEstimating, setIsEstimating] = useState(false)
  const [estimateError, setEstimateError] = useState<string | null>(null)
  const [estimateResult, setEstimateResult] = useState<{
    title?: string
    duration_min?: number
    time_est_min?: number
    calls?: number
  } | null>(null)

  const handleInspectUrl = async (e: React.FormEvent) => {
    e.preventDefault()
    const trimmed = pasteUrl.trim()
    if (!trimmed) return
    if (!trimmed.includes('youtube.com/') && !trimmed.includes('youtu.be/')) {
      setEstimateError('Please paste a valid YouTube lecture link (e.g. https://www.youtube.com/watch?v=...)')
      return
    }
    setIsEstimating(true)
    setEstimateError(null)
    setEstimateResult(null)
    try {
      const fd = new FormData()
      fd.append('source_type', 'youtube')
      fd.append('url', trimmed)
      const res = await fetch('/estimate', { method: 'POST', body: fd })
      if (!res.ok) {
        setEstimateError('Could not inspect this YouTube video. Check the link or privacy settings.')
        return
      }
      const data = await res.json()
      if (data.available) {
        setEstimateResult(data)
      } else {
        setEstimateError(data.reason || 'Could not read duration for this lecture.')
      }
    } catch {
      setEstimateError('Failed to inspect video. Please try again.')
    } finally {
      setIsEstimating(false)
    }
  }

  const demoHref = `/workspace/${PRIMARY_DEMO_LECTURE_ID}`

  return (
    <div id="main" className="min-h-screen bg-nb text-nt font-sans overflow-x-hidden">
      <header className="sticky top-0 z-40 border-b border-bdr bg-nb/95 backdrop-blur-sm">
        <Container className="flex items-center justify-between gap-4 py-3">
          <Link to="/" className={`rounded-sm ${LINK_RING}`} aria-label="NorAI home">
            <Wordmark size="md" />
          </Link>

          <nav aria-label="Main" className="hidden md:flex items-center gap-7 text-15 text-nt2">
            {navLinks}
          </nav>

          <div className="flex items-center gap-2">
            {user ? (
              <>
                <button
                  onClick={() => void signOut()}
                  className={`hidden sm:inline-flex items-center gap-1.5 px-2.5 py-1.5 text-15 text-nt2 hover:text-nrt cursor-pointer ${FOCUS_RING} rounded-md`}
                >
                  <LogOut size={15} aria-hidden="true" /> Sign out
                </button>
                <button
                  onClick={onStartWorkspace}
                  className={`inline-flex items-center gap-1.5 rounded-md bg-npf px-4 h-10 text-15 font-bold text-npfg hover:bg-npfh active:translate-y-px cursor-pointer transition-colors ${FOCUS_RING}`}
                >
                  Open your library <ArrowRight size={15} aria-hidden="true" />
                </button>
              </>
            ) : (
              <>
                <Link to="/login" className={`hidden sm:inline-block px-2.5 py-1.5 text-15 text-nt2 hover:text-nt ${LINK_RING}`}>
                  Log in
                </Link>
                <Link
                  to="/signup"
                  className={`inline-flex items-center rounded-md bg-npf px-4 h-10 text-15 font-bold text-npfg hover:bg-npfh active:translate-y-px transition-colors ${FOCUS_RING}`}
                >
                  Start free
                </Link>
              </>
            )}
            <button
              onClick={() => setMenuOpen((o) => !o)}
              className={`md:hidden -mr-1 rounded-md p-2 text-nt2 hover:bg-ns2 hover:text-nt cursor-pointer ${FOCUS_RING}`}
              aria-label={menuOpen ? 'Close menu' : 'Open menu'}
              aria-expanded={menuOpen}
              aria-controls="mobile-nav"
            >
              {menuOpen ? <X size={20} /> : <Menu size={20} />}
            </button>
          </div>
        </Container>
        {menuOpen && (
          <nav id="mobile-nav" aria-label="Main" className="md:hidden flex flex-col gap-4 border-t border-bdr bg-ns px-4 py-5 text-16 text-nt2">
            {navLinks}
            {user ? (
              <button onClick={() => void signOut()} className="flex items-center gap-2 text-left text-nt2 hover:text-nrt cursor-pointer">
                <LogOut size={15} aria-hidden="true" /> Sign out
              </button>
            ) : (
              <Link to="/login" className="hover:text-nt">Log in</Link>
            )}
          </nav>
        )}
      </header>

      {/* Hero: the promise, and a stack sign for a real lecture */}
      <section className="pt-12 sm:pt-20 pb-16 sm:pb-24">
        <Container className="grid gap-12 lg:grid-cols-[1.15fr_0.85fr] lg:items-center lg:gap-16">
          <div>
            <h1 className="max-w-3xl font-serif font-semibold text-[clamp(2.5rem,5.6vw,4.25rem)] leading-[1.04] tracking-[-0.02em] text-balance">
              {youtubeOn ? (
                <>Turn lecture videos into <span className="whitespace-nowrap">exam-ready</span> notes.</>
              ) : (
                <>Turn any lecture, PDF or slide deck into <span className="whitespace-nowrap">exam-ready</span> notes.</>
              )}
            </h1>
            <p className="mt-6 max-w-[38rem] text-18 leading-relaxed text-nt2">
              {youtubeOn
                ? 'Paste a YouTube link or upload your class recording. '
                : 'Upload a class recording, PDF, Word file or slide deck, or paste a Google Drive or web link. '}
              NorAI writes chapter-wise study notes, a revision sheet, a quiz and flashcards, and gives you a tutor
              that answers only from {youtubeOn ? 'that lecture, down to the minute it was said' : 'your material, down to the minute or page it came from'}.
            </p>

            {/* Paste-first YouTube Onboarding */}
            {youtubeOn && (
            <form onSubmit={handleInspectUrl} className="mt-8 max-w-xl">
              <div className="flex flex-col sm:flex-row gap-2">
                <div className="relative flex-1">
                  <input
                    type="url"
                    value={pasteUrl}
                    onChange={(e) => {
                      setPasteUrl(e.target.value)
                      if (estimateError) setEstimateError(null)
                    }}
                    placeholder="Paste a YouTube lecture link…"
                    className={`w-full h-12 px-4 rounded-md bg-ns border border-bdr text-15 text-nt placeholder:text-nt3 ${FOCUS_RING}`}
                    aria-label="YouTube lecture URL"
                  />
                </div>
                <button
                  type="submit"
                  disabled={isEstimating || !pasteUrl.trim()}
                  className="h-12 px-5 rounded-md bg-npf text-npfg hover:bg-npfh text-15 font-bold shrink-0 disabled:opacity-50 cursor-pointer transition-colors"
                >
                  {isEstimating ? 'Inspecting…' : 'Preview Study Pack'}
                </button>
              </div>

              {estimateError && (
                <p className="mt-2 text-13 text-nrt">{estimateError}</p>
              )}

              {estimateResult && (
                <div className="mt-4 p-4 rounded-lg bg-ns border border-bdr text-left shadow-ev1">
                  <div className="flex items-center justify-between gap-2 mb-1.5">
                    <span className="spec-label text-np font-bold">Ready to process</span>
                    <span className="text-12 font-mono text-nt3">
                      {estimateResult.duration_min ? `${Math.round(estimateResult.duration_min)} min lecture` : 'Detected'}
                    </span>
                  </div>
                  <p className="text-15 font-bold text-nt truncate mb-2">
                    {estimateResult.title || pasteUrl}
                  </p>
                  <p className="text-13 text-nt2 mb-3">
                    Generates chapter notes, revision sheet, practice quiz, flashcards & Nora AI tutor in ~{Math.ceil(estimateResult.time_est_min || 3)} min.
                  </p>
                  <button
                    type="button"
                    onClick={() => {
                      if (user) {
                        onStartWorkspace()
                      } else {
                        navigate(`/signup?url=${encodeURIComponent(pasteUrl)}`)
                      }
                    }}
                    className={PRIMARY_BTN + ' h-10 text-14 px-4'}
                  >
                    {user ? 'Process in your library' : 'Start free: generate pack'}
                    <ArrowRight size={15} />
                  </button>
                </div>
              )}
            </form>
            )}

            <div className="mt-8 flex flex-col sm:flex-row sm:items-center gap-3 sm:gap-6">
              <button onClick={start} className={PRIMARY_BTN}>
                {user ? 'Open your library' : 'Start free: no card needed'}
                <ArrowRight size={17} aria-hidden="true" />
              </button>
              <Link
                to={demoHref}
                className={`inline-flex items-center justify-center gap-1.5 px-1 py-2 text-16 font-bold text-np underline decoration-2 underline-offset-[6px] decoration-np/30 hover:decoration-np ${LINK_RING}`}
              >
                See a finished lecture first
              </Link>
            </div>
            <p className="mt-5 text-14 text-nt3">
              Free for every student: {FREE_MINUTES} lecture-minutes a month, every feature included.
            </p>
          </div>

          {/* Stack sign: the demo lecture's chapters as call ranges */}
          <Link
            to={demoHref}
            aria-label="Open the demo lecture: Algorithms and Computation"
            className={`rail group block rounded-lg p-5 sm:p-6 ${FOCUS_RING}`}
          >
            <div className="flex items-baseline justify-between gap-3">
              <span className="spec-label">Demo lecture</span>
              <span className="font-mono text-13 text-nt3">45 min · 9 chapters</span>
            </div>
            <p className="mt-2 text-20 font-bold leading-snug">Algorithms and Computation</p>
            <ul className="mt-5 space-y-1.5" aria-hidden="true">
              {DEMO_RANGES.map((r, i) => (
                <li
                  key={r.ch}
                  data-current={i === 0 ? 'true' : undefined}
                  className="rail-range grid grid-cols-[auto_1fr] items-center gap-3 rounded-md px-2.5 py-2"
                >
                  <ShelfMark top={`CH ${r.ch}`} time={r.at} className="min-w-[56px]" />
                  <span className={`text-15 leading-snug ${i === 0 ? 'font-bold' : ''}`}>{r.title}</span>
                </li>
              ))}
            </ul>
            <span className="mt-5 inline-flex items-center gap-1.5 text-15 font-bold text-np group-hover:underline underline-offset-4">
              Open this lecture <ArrowRight size={16} aria-hidden="true" />
            </span>
          </Link>
        </Container>

        {/* The real product */}
        <Container className="mt-16 sm:mt-20">
          <figure>
            <div className="overflow-hidden rounded-lg border border-bdr2 bg-ns shadow-ev3">
              {/* Phones get the tutor panel alone so its text stays readable. */}
              <picture>
                <source media="(max-width: 767px)" srcSet="/landing/tutor-mobile.webp" width={722} height={960} />
                <img
                  src="/landing/notes-and-tutor.webp"
                  alt="NorAI workspace: chapter notes with timestamps, beside Nora answering a question from the lecture with its sources."
                  width={1600}
                  height={936}
                  fetchPriority="high"
                  decoding="async"
                  className="block h-auto w-full"
                />
              </picture>
            </div>
            <figcaption className="mt-4 text-15 text-nt2 max-w-2xl">
              Every chapter, section and answer carries a shelf mark. Press one and the video plays from that moment.
            </figcaption>
          </figure>
        </Container>
      </section>

      {/* What one lecture becomes */}
      <section aria-labelledby="outputs-heading" className="border-t border-bdr py-20 sm:py-28">
        <Container>
          <h2 id="outputs-heading" className="max-w-3xl font-serif font-semibold text-36 sm:text-44 leading-tight tracking-tight text-balance">
            One lecture in. Six ways to study it.
          </h2>
          <dl className="mt-12 divide-y divide-bdr border-y border-bdr">
            {OUTPUTS.map((o) => (
              <div key={o.name} className="grid gap-1.5 py-5 sm:grid-cols-[14rem_1fr] sm:gap-8">
                <dt className="flex items-center gap-3 text-18 font-bold text-nt">
                  <span aria-hidden="true" className={`w-3 h-3 rounded-[2px] ${o.zone}`} />
                  {o.name}
                </dt>
                <dd className="max-w-[62ch] text-16 leading-relaxed text-nt2">{o.body}</dd>
              </div>
            ))}
          </dl>
        </Container>
      </section>

      {/* Quiz proof */}
      <section aria-labelledby="quiz-heading" className="bg-ns border-y border-bdr py-20 sm:py-28">
        <Container className="grid items-center gap-12 lg:grid-cols-[1fr_1.15fr]">
          <div>
            <h2 id="quiz-heading" className="font-serif font-semibold text-36 leading-tight tracking-tight text-balance">
              Find the gaps before the exam does.
            </h2>
            <p className="mt-5 max-w-md text-16 leading-relaxed text-nt2">
              Every lecture comes with its own question bank, written from what was actually taught. Get one wrong and
              “Explain” shows the part of the notes it came from. Your attempts are saved, so you can retake only the
              ones you missed.
            </p>
          </div>
          <img
            src="/landing/quiz.webp"
            alt="A NorAI quiz question: for a 28 by 28 pixel image, how many neurons are needed in the input layer, with four options."
            width={1000}
            height={716}
            loading="lazy"
            decoding="async"
            className="w-full rounded-lg border border-bdr2 shadow-ev2"
          />
        </Container>
      </section>

      {/* Demo lectures: a catalogue, each with its call number */}
      <section id="demo" aria-labelledby="demo-heading" className="py-20 sm:py-28">
        <Container>
          <h2 id="demo-heading" className="max-w-2xl font-serif font-semibold text-36 sm:text-44 leading-tight tracking-tight text-balance">
            Open a lecture we already processed.
          </h2>
          <p className="mt-4 max-w-xl text-16 text-nt2">No account needed. Read the notes, take the quiz, flip the cards.</p>
          <ol className="mt-10 border-t border-bdr2">
            {DEMO_LECTURES_CONFIG.map((demo) => (
              <li key={demo.id} className="border-b border-bdr2 py-6">
                <div className="grid grid-cols-[auto_1fr] gap-x-4 sm:gap-x-6 gap-y-3 sm:grid-cols-[auto_1fr_auto] sm:items-center">
                  <Link to={`/workspace/${demo.id}`} className="shrink-0">
                    <ShelfMark
                      top={DEMO_CODES[demo.category] ?? 'LEC'}
                      time={demo.duration}
                      className="min-w-[64px]"
                    />
                  </Link>
                  <div>
                    <Link
                      to={`/workspace/${demo.id}`}
                      className="block text-20 sm:text-22 font-bold text-nt hover:text-np transition-colors"
                    >
                      {demo.title}
                    </Link>
                    <p className="mt-1 max-w-[62ch] text-15 text-nt2">{demo.summary}</p>
                    {DEMO_SLUGS[demo.id] && (
                      <div className="mt-2 flex items-center gap-4 text-13">
                        <Link
                          to={`/demo/${DEMO_SLUGS[demo.id]}`}
                          className="font-medium text-np hover:underline underline-offset-4"
                        >
                          Read answer-first study guide & syllabus →
                        </Link>
                      </div>
                    )}
                  </div>
                  <div className="col-start-2 sm:col-start-auto flex items-center gap-3 text-14 text-nt3 sm:whitespace-nowrap">
                    <span>{demo.chapterCount} chapters</span>
                    <Link
                      to={`/workspace/${demo.id}`}
                      aria-label={`Open ${demo.title}`}
                      className="p-1 rounded text-np hover:bg-ns2"
                    >
                      <ArrowUpRight size={18} aria-hidden="true" />
                    </Link>
                  </div>
                </div>
              </li>
            ))}
          </ol>
        </Container>
      </section>

      {/* How it works */}
      <section id="how-it-works" aria-labelledby="how-heading" className="bg-ns border-y border-bdr py-20 sm:py-28">
        <Container>
          <h2 id="how-heading" className="font-serif font-semibold text-36 sm:text-44 leading-tight tracking-tight">
            How it works
          </h2>
          <ol className="mt-12 grid gap-10 md:grid-cols-3 md:gap-8">
            {STEPS.map((s, i) => (
              <li key={s.title} className="border-t-2 border-nt pt-5">
                <span className="font-mono text-15 font-semibold text-np">{String(i + 1).padStart(2, '0')}</span>
                <h3 className="mt-2 text-20 font-bold leading-snug text-nt">{s.title}</h3>
                <p className="mt-3 text-15 leading-relaxed text-nt2">{s.body}</p>
              </li>
            ))}
          </ol>
        </Container>
      </section>

      {/* Free: what the allowance covers */}
      <section id="pricing" aria-labelledby="pricing-heading" className="py-20 sm:py-28">
        <Container className="grid gap-10 lg:grid-cols-[1fr_1.1fr] lg:gap-16">
          <div>
            <h2 id="pricing-heading" className="max-w-xl font-serif font-semibold text-36 sm:text-44 leading-tight tracking-tight text-balance">
              Free. All of it.
            </h2>
            <p className="mt-5 max-w-md text-16 leading-relaxed text-nt2">
              Every account gets {FREE_MINUTES} lecture-minutes every 30 days, with nothing held back for a paid tier.
              Everything you process stays in your library, and studying it again never uses minutes.
            </p>
            <button onClick={start} className={`mt-8 ${PRIMARY_BTN}`}>
              {user ? 'Open your library' : 'Create a free account'} <ArrowRight size={17} aria-hidden="true" />
            </button>
          </div>
          <dl className="divide-y divide-bdr border-y border-bdr self-start">
            {[
              [`${FREE_MINUTES} minutes`, 'Of new lectures, every 30 days. A 45-minute class uses 45.'],
              ['Every feature', 'Notes, revision sheet, quiz, flashcards, mind map, PDF export and the tutor.'],
              ['No card', 'Sign up with an email. Nothing to cancel, nothing that renews.'],
              ['Yours to keep', 'Re-reading notes, retaking quizzes and asking the tutor never use minutes.'],
            ].map(([term, body]) => (
              <div key={term} className="grid gap-1 py-4 sm:grid-cols-[10rem_1fr] sm:gap-6">
                <dt className="text-17 font-bold text-nt">{term}</dt>
                <dd className="text-15 leading-relaxed text-nt2">{body}</dd>
              </div>
            ))}
          </dl>
        </Container>
      </section>

      {/* FAQ: answer-first, mirrored in the FAQPage JSON-LD */}
      <section id="faq" aria-labelledby="faq-heading" className="border-t border-bdr py-20 sm:py-28">
        <Container>
          <h2 id="faq-heading" className="font-serif font-semibold text-36 sm:text-44 leading-tight tracking-tight">
            Questions students ask
          </h2>
          <div className="mt-10 max-w-3xl">
            <FaqList items={HOME_FAQ} />
          </div>
        </Container>
      </section>

      {/* Closing, on the green of the stacks */}
      <section className="rail py-20 sm:py-24">
        <Container className="flex flex-col gap-8 md:flex-row md:items-end md:justify-between">
          <p className="max-w-2xl font-serif font-semibold text-36 sm:text-44 leading-tight tracking-tight text-balance">
            Your next lecture, already revised.
          </p>
          <button onClick={start} className={`shrink-0 ${PRIMARY_BTN}`}>
            {user ? 'Open your library' : 'Start free'} <ArrowRight size={17} aria-hidden="true" />
          </button>
        </Container>
      </section>

      <footer className="border-t border-bdr bg-nb py-10 text-14 text-nt3">
        <Container className="flex flex-col gap-6 sm:flex-row sm:items-center sm:justify-between">
          <p className="flex flex-wrap items-center gap-x-3 gap-y-2">
            <Wordmark size="sm" />
            <span>Study notes and a tutor from your lectures. © 2026</span>
          </p>
          <nav aria-label="Footer" className="flex flex-wrap gap-x-6 gap-y-2">
            <Link to="/pricing" className={`hover:text-nt ${LINK_RING}`}>Free plan</Link>
            <a href="#demo" className={`hover:text-nt ${LINK_RING}`}>Demo lectures</a>
            <Link to="/signup" className={`hover:text-nt ${LINK_RING}`}>Sign up</Link>
            <Link to="/login" className={`hover:text-nt ${LINK_RING}`}>Log in</Link>
          </nav>
        </Container>
      </footer>
    </div>
  )
}
