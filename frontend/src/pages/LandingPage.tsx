import { useState, type ReactNode } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { ArrowRight, ArrowUpRight, LogOut, Menu, X } from 'lucide-react'
import { useAuthStore } from '../stores/useAuthStore'
import { FOCUS_RING, LINK_RING } from '../components/ui/shared'
import { DEMO_LECTURES_CONFIG, PRIMARY_DEMO_LECTURE_ID } from '../config/features'
import { FaqList } from '../components/marketing/FaqList'
import { FREE_MINUTES, HOME_FAQ } from '../content/faq'
import { PAGE_META } from '../content/pages'
import { usePageMeta } from '../lib/usePageMeta'

interface LandingPageProps {
  onStartWorkspace: () => void
}

/** What one processed lecture contains — a ruled list, not a card grid. */
const OUTPUTS = [
  {
    name: 'Study notes',
    body: 'Chapter-wise notes in the order your professor taught, with formulas typeset properly and the slides that mattered pulled out of the video.',
  },
  {
    name: 'Revision sheet',
    body: 'The night-before version: key takeaways and definitions per chapter, short enough to read on the bus.',
  },
  {
    name: 'Quiz',
    body: 'MCQ and true/false questions at three difficulty levels, each linked back to the notes so you can see why an answer is right.',
  },
  {
    name: 'Flashcards',
    body: 'A deck for every lecture. Rate each card and spaced-repetition scheduling brings back the ones you keep missing.',
  },
  {
    name: 'Tutor',
    body: 'Ask doubts in plain words. Nora answers only from your lecture and tells you which part of the video it is quoting.',
  },
  {
    name: 'Mind map',
    body: 'Each chapter as a concept tree, for when you need to see how the topics connect before an exam.',
  },
] as const

const STEPS = [
  {
    title: 'Paste a YouTube link or upload the recording',
    body: 'MP4, MOV, MKV, AVI or WebM. A recorded class, a university lecture, an online course: anything with someone teaching.',
  },
  {
    title: 'Check the estimate, then let it run',
    body: 'You see how many minutes it will use before anything starts. Close the tab if you like; it keeps working.',
  },
  {
    title: 'Study from it',
    body: 'Notes, revision sheet, quiz, flashcards and the tutor open together in one workspace, and stay in your library.',
  },
] as const

/** The red margin rule of a ruled notebook; content sits to its right on md+. */
function Margin({ children, className = '' }: { children: ReactNode; className?: string }) {
  return (
    <div className={`relative mx-auto w-full max-w-6xl px-4 sm:px-6 md:pl-28 ${className}`}>
      <span aria-hidden="true" className="pointer-events-none absolute inset-y-0 left-[4.5rem] hidden w-px bg-np/35 md:block" />
      {children}
    </div>
  )
}

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
      <a href="#demo" className={`hover:text-nt transition-colors ${LINK_RING}`} onClick={() => setMenuOpen(false)}>Demo</a>
      <Link to="/pricing" className={`hover:text-nt transition-colors ${LINK_RING}`}>It's free</Link>
      <a href="#faq" className={`hover:text-nt transition-colors ${LINK_RING}`} onClick={() => setMenuOpen(false)}>FAQ</a>
    </>
  )

  return (
    <div id="main" className="min-h-screen bg-nb text-nt font-sans selection:bg-npb selection:text-npt overflow-x-hidden">
      <header className="sticky top-0 z-40 border-b border-bdr bg-nb/92 backdrop-blur-sm">
        <div className="mx-auto flex max-w-6xl items-center justify-between gap-4 px-4 sm:px-6 py-3">
          <Link to="/" className={`font-serif text-22 tracking-tight text-nt ${LINK_RING}`} aria-label="NorAI home">
            Nor<span className="text-np">AI</span>
          </Link>

          <nav aria-label="Main" className="hidden md:flex items-center gap-7 text-13 text-nt2">
            {navLinks}
          </nav>

          <div className="flex items-center gap-2">
            {user ? (
              <>
                <button
                  onClick={() => void signOut()}
                  className={`hidden sm:inline-flex items-center gap-1.5 px-2.5 py-1.5 text-13 text-nt2 hover:text-nrt cursor-pointer ${FOCUS_RING} rounded-md`}
                >
                  <LogOut size={14} aria-hidden="true" /> Sign out
                </button>
                <button
                  onClick={onStartWorkspace}
                  className={`inline-flex items-center gap-1.5 rounded-md bg-npf px-4 py-2 text-13 font-medium text-npfg hover:bg-npfh active:translate-y-px cursor-pointer transition-colors ${FOCUS_RING}`}
                >
                  Open workspace <ArrowRight size={14} aria-hidden="true" />
                </button>
              </>
            ) : (
              <>
                <Link to="/login" className={`hidden sm:inline-block px-2.5 py-1.5 text-13 text-nt2 hover:text-nt ${LINK_RING}`}>
                  Log in
                </Link>
                <Link
                  to="/signup"
                  className={`inline-flex items-center rounded-md bg-npf px-4 py-2 text-13 font-medium text-npfg hover:bg-npfh active:translate-y-px transition-colors ${FOCUS_RING}`}
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
              {menuOpen ? <X size={18} /> : <Menu size={18} />}
            </button>
          </div>
        </div>
        {menuOpen && (
          <nav id="mobile-nav" aria-label="Main" className="md:hidden flex flex-col gap-4 border-t border-bdr bg-ns px-4 py-5 text-15 text-nt2">
            {navLinks}
            {user ? (
              <button onClick={() => void signOut()} className="flex items-center gap-2 text-left text-nt2 hover:text-nrt cursor-pointer">
                <LogOut size={14} aria-hidden="true" /> Sign out
              </button>
            ) : (
              <Link to="/login" className="hover:text-nt">Log in</Link>
            )}
          </nav>
        )}
      </header>

      {/* Hero — on faint notebook ruling */}
      <section className="relative pt-12 sm:pt-20 pb-20 sm:pb-28 notebook-ruling">
        <Margin>
          <h1 className="max-w-4xl font-serif text-[clamp(2.5rem,6.2vw,4.75rem)] leading-[1.02] tracking-[-0.025em] text-balance">
            Turn lecture videos into <em className="text-np">exam-ready</em> notes.
          </h1>
          <p className="mt-6 max-w-2xl text-17 leading-relaxed text-nt2">
            Paste a YouTube link or upload your class recording. NorAI writes chapter-wise study notes, a revision
            sheet, a quiz and flashcards, and gives you a tutor that answers only from that lecture.
          </p>
          <div className="mt-9 flex flex-col sm:flex-row sm:items-center gap-3 sm:gap-5">
            <button
              onClick={start}
              className={`inline-flex items-center justify-center gap-2 rounded-md bg-npf px-6 py-3.5 text-15 font-medium text-npfg shadow-bp hover:bg-npfh active:translate-y-px cursor-pointer transition-colors ${FOCUS_RING}`}
            >
              {user ? 'Open your workspace' : 'Start free: no card needed'}
              <ArrowRight size={16} aria-hidden="true" />
            </button>
            <Link
              to={`/workspace/${PRIMARY_DEMO_LECTURE_ID}`}
              className={`inline-flex items-center justify-center gap-1.5 px-1 py-2 text-15 text-nt underline decoration-np/50 decoration-2 underline-offset-[6px] hover:decoration-np ${LINK_RING}`}
            >
              See a finished lecture first
            </Link>
          </div>
          <p className="mt-5 text-13 text-nt3">
            Free for every student: {FREE_MINUTES} lecture-minutes a month, every feature included.
          </p>
        </Margin>

        {/* The real product, with one red-pencil annotation drawn on */}
        <div className="relative mx-auto mt-14 sm:mt-20 max-w-6xl px-4 sm:px-6">
          <figure className="relative">
            <div className="overflow-hidden rounded-lg border border-bdr2 bg-ns shadow-[0_24px_60px_-28px_rgba(36,31,26,0.35)]">
              {/* Phones get the tutor panel alone so its text stays readable. */}
              <picture>
                <source media="(max-width: 767px)" srcSet="/landing/tutor-mobile.webp" width={722} height={960} />
                <img
                  src="/landing/notes-and-tutor.webp"
                  alt="NorAI workspace: chapter notes on neural networks beside the tutor answering why the input layer has 784 neurons, quoting the lecture slide."
                  width={1600}
                  height={936}
                  fetchPriority="high"
                  decoding="async"
                  className="block h-auto w-full"
                />
              </picture>
            </div>
            <svg
              aria-hidden="true"
              viewBox="0 0 1600 936"
              preserveAspectRatio="none"
              className="pointer-events-none absolute inset-0 hidden h-full w-full md:block"
            >
              <path
                className="pencil-draw"
                pathLength={1}
                d="M1116 454 C 1300 442, 1592 448, 1594 515 C 1596 582, 1380 588, 1182 585 C 1096 583, 1092 530, 1104 490 C 1110 470, 1132 459, 1170 455"
                fill="none"
                stroke="var(--color-np)"
                strokeWidth="4"
                strokeLinecap="round"
              />
            </svg>
            <figcaption className="mt-4 text-13 text-nt2 md:absolute md:-bottom-3 md:right-10 md:mt-0 md:max-w-xs md:translate-y-full md:text-right">
              <span className="font-serif italic text-15 text-npt">
                Answered from the lecture itself, down to the slide it came from.
              </span>
            </figcaption>
          </figure>
        </div>
      </section>

      {/* What one lecture becomes */}
      <section aria-labelledby="outputs-heading" className="border-t border-bdr py-20 sm:py-28">
        <Margin>
          <h2 id="outputs-heading" className="max-w-3xl font-serif text-36 sm:text-44 leading-tight tracking-tight text-balance">
            One lecture in. Six ways to study it out.
          </h2>
          <dl className="mt-12 divide-y divide-bdr border-y border-bdr">
            {OUTPUTS.map((o) => (
              <div key={o.name} className="grid gap-1 py-5 sm:grid-cols-[13rem_1fr] sm:gap-8">
                <dt className="font-serif text-22 text-nt">{o.name}</dt>
                <dd className="max-w-prose text-15 leading-relaxed text-nt2">{o.body}</dd>
              </div>
            ))}
          </dl>
        </Margin>
      </section>

      {/* Quiz proof */}
      <section aria-labelledby="quiz-heading" className="bg-ns border-y border-bdr py-20 sm:py-28">
        <Margin className="grid items-center gap-12 lg:grid-cols-[1fr_1.15fr]">
          <div>
            <h2 id="quiz-heading" className="font-serif text-36 leading-tight tracking-tight text-balance">
              Find the gaps before the exam does.
            </h2>
            <p className="mt-5 max-w-md text-15 leading-relaxed text-nt2">
              Every lecture comes with its own question bank, written from what was actually taught. Get one wrong and
              “Explain” shows you the exact part of the notes it came from. Your attempts are saved, so you can retake
              only the ones you missed.
            </p>
          </div>
          <img
            src="/landing/quiz.webp"
            alt="A NorAI quiz question: for a 28 by 28 pixel image, how many neurons are needed in the input layer, with four options."
            width={1000}
            height={716}
            loading="lazy"
            decoding="async"
            className="w-full rounded-lg border border-bdr2 shadow-[0_18px_40px_-24px_rgba(36,31,26,0.35)]"
          />
        </Margin>
      </section>

      {/* Demo lectures — a table of contents, not cards */}
      <section id="demo" aria-labelledby="demo-heading" className="py-20 sm:py-28">
        <Margin>
          <h2 id="demo-heading" className="max-w-2xl font-serif text-36 sm:text-44 leading-tight tracking-tight text-balance">
            Open a lecture we already processed.
          </h2>
          <p className="mt-4 max-w-xl text-15 text-nt2">No account needed. Read the notes, take the quiz, flip the cards.</p>
          <ol className="mt-10 border-t border-bdr2">
            {DEMO_LECTURES_CONFIG.map((demo) => (
              <li key={demo.id} className="border-b border-bdr2">
                <Link
                  to={`/workspace/${demo.id}`}
                  className={`group grid gap-2 py-6 sm:grid-cols-[1fr_auto] sm:items-baseline sm:gap-8 ${LINK_RING}`}
                >
                  <span>
                    <span className="block font-serif text-22 sm:text-24 text-nt group-hover:text-npt transition-colors">
                      {demo.title}
                    </span>
                    <span className="mt-1 block max-w-2xl text-14 text-nt2">{demo.summary}</span>
                  </span>
                  <span className="flex items-center gap-3 text-13 text-nt3 tabular-nums sm:whitespace-nowrap">
                    {demo.category} · {demo.duration} · {demo.chapterCount} chapters
                    <ArrowUpRight size={16} aria-hidden="true" className="shrink-0 text-np transition-transform group-hover:-translate-y-0.5 group-hover:translate-x-0.5" />
                  </span>
                </Link>
              </li>
            ))}
          </ol>
        </Margin>
      </section>

      {/* How it works */}
      <section id="how-it-works" aria-labelledby="how-heading" className="bg-ns border-y border-bdr py-20 sm:py-28">
        <Margin>
          <h2 id="how-heading" className="font-serif text-36 sm:text-44 leading-tight tracking-tight">
            How it works
          </h2>
          <ol className="mt-12 grid gap-10 md:grid-cols-3 md:gap-8">
            {STEPS.map((s, i) => (
              <li key={s.title} className="border-t-2 border-nt pt-5">
                <h3 className="font-serif text-20 leading-snug text-nt">
                  <span className="mr-2 text-np">{i + 1}.</span>
                  {s.title}
                </h3>
                <p className="mt-3 text-14 leading-relaxed text-nt2">{s.body}</p>
              </li>
            ))}
          </ol>
        </Margin>
      </section>

      {/* Free — what the allowance covers */}
      <section id="pricing" aria-labelledby="pricing-heading" className="py-20 sm:py-28">
        <Margin className="grid gap-10 lg:grid-cols-[1fr_1.1fr] lg:gap-16">
          <div>
            <h2 id="pricing-heading" className="max-w-xl font-serif text-36 sm:text-44 leading-tight tracking-tight text-balance">
              Free. All of it.
            </h2>
            <p className="mt-5 max-w-md text-15 leading-relaxed text-nt2">
              Every account gets {FREE_MINUTES} lecture-minutes every 30 days, with nothing held back for a paid tier.
              Everything you process stays in your library, and studying it again never uses minutes.
            </p>
            <button
              onClick={start}
              className={`mt-8 inline-flex items-center justify-center gap-2 rounded-md bg-npf px-6 py-3 text-15 font-medium text-npfg hover:bg-npfh active:translate-y-px cursor-pointer transition-colors ${FOCUS_RING}`}
            >
              {user ? 'Open your workspace' : 'Create a free account'} <ArrowRight size={16} aria-hidden="true" />
            </button>
          </div>
          <dl className="divide-y divide-bdr border-y border-bdr self-start">
            {[
              [`${FREE_MINUTES} minutes`, 'Of new lectures, every 30 days. A 45-minute class uses 45.'],
              ['Every feature', 'Notes, revision sheet, quiz, flashcards, mind map, PDF export and the tutor.'],
              ['No card', 'Sign up with an email. Nothing to cancel, nothing that renews.'],
              ['Yours to keep', 'Re-reading notes, retaking quizzes and asking the tutor never use minutes.'],
            ].map(([term, body]) => (
              <div key={term} className="grid gap-1 py-4 sm:grid-cols-[9.5rem_1fr] sm:gap-6">
                <dt className="font-serif text-20 text-nt">{term}</dt>
                <dd className="text-14 leading-relaxed text-nt2">{body}</dd>
              </div>
            ))}
          </dl>
        </Margin>
      </section>

      {/* FAQ — answer-first, also mirrored in index.html JSON-LD */}
      <section id="faq" aria-labelledby="faq-heading" className="border-t border-bdr py-20 sm:py-28">
        <Margin>
          <h2 id="faq-heading" className="font-serif text-36 sm:text-44 leading-tight tracking-tight">
            Questions students ask
          </h2>
          <div className="mt-10 max-w-3xl">
            <FaqList items={HOME_FAQ} />
          </div>
        </Margin>
      </section>

      {/* Closing */}
      <section className="bg-nt text-nb py-20 sm:py-24">
        <Margin className="flex flex-col gap-8 md:flex-row md:items-end md:justify-between">
          <p className="max-w-2xl font-serif text-36 sm:text-44 leading-tight tracking-tight text-balance">
            Your next lecture, already revised.
          </p>
          <button
            onClick={start}
            className={`inline-flex shrink-0 items-center justify-center gap-2 rounded-md bg-npf px-6 py-3.5 text-15 font-medium text-npfg hover:bg-npfh active:translate-y-px cursor-pointer transition-colors ${FOCUS_RING}`}
          >
            {user ? 'Open your workspace' : 'Start free'} <ArrowRight size={16} aria-hidden="true" />
          </button>
        </Margin>
      </section>

      <footer className="border-t border-bdr bg-nb py-10 text-13 text-nt3">
        <div className="mx-auto flex max-w-6xl flex-col gap-6 px-4 sm:px-6 sm:flex-row sm:items-center sm:justify-between">
          <p>
            <span className="font-serif text-17 text-nt">Nor<span className="text-np">AI</span></span>
            <span className="ml-3">Study notes and a tutor from your lectures. © 2026</span>
          </p>
          <nav aria-label="Footer" className="flex flex-wrap gap-x-6 gap-y-2">
            <Link to="/pricing" className={`hover:text-nt ${LINK_RING}`}>Free plan</Link>
            <a href="#demo" className={`hover:text-nt ${LINK_RING}`}>Demo lectures</a>
            <Link to="/signup" className={`hover:text-nt ${LINK_RING}`}>Sign up</Link>
            <Link to="/login" className={`hover:text-nt ${LINK_RING}`}>Log in</Link>
          </nav>
        </div>
      </footer>
    </div>
  )
}
