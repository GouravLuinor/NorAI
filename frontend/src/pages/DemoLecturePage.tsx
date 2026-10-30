import { useParams, Link, useNavigate } from 'react-router-dom'
import { DEMO_PAGES } from '../content/demoPages'
import { Wordmark } from '../components/brand/Wordmark'
import { ShelfMark } from '../components/ui/ShelfMark'
import { Button } from '../components/ui/Button'
import { LINK_RING } from '../components/ui/shared'
import { usePageMeta } from '../lib/usePageMeta'
import { ArrowRight, BookOpen, Brain, Check, HelpCircle, Sparkles } from 'lucide-react'

export function DemoLecturePage({ initialSlug }: { initialSlug?: string }) {
  const params = useParams<{ slug: string }>()
  const navigate = useNavigate()
  const slug = initialSlug || params.slug || 'algorithms-and-computation'
  const data = DEMO_PAGES[slug]

  usePageMeta({
    title: data?.metaTitle || 'Demo Lecture Study Guide — NorAI',
    description: data?.description || 'Study guide, lecture notes, quiz, flashcards, and AI tutor for this lecture.',
    path: `/demo/${slug}`,
  })

  if (!data) {
    return (
      <div id="main" className="min-h-screen bg-nb text-nt flex flex-col items-center justify-center p-6 text-center">
        <Wordmark size="md" className="mb-6" />
        <h1 className="font-serif text-28 font-bold mb-3">Demo Lecture Not Found</h1>
        <p className="text-15 text-nt2 mb-6 max-w-md">
          We couldn't locate this public demo lecture. Explore all 5 featured demo lectures on our homepage.
        </p>
        <Button onClick={() => navigate('/')} className="px-6 h-11 text-15 font-bold">
          Return Home
        </Button>
      </div>
    )
  }

  const workspaceHref = `/workspace/${data.lectureId}`

  // Schema.org structured data for this learning resource
  const learningResourceJsonLd = {
    '@context': 'https://schema.org',
    '@type': 'LearningResource',
    name: data.title,
    description: data.description,
    educationalLevel: 'Higher Education',
    learningResourceType: 'Study Guide and Interactive Workspace',
    provider: {
      '@type': 'Organization',
      name: 'NorAI',
      url: 'https://norai.app',
    },
    educationalUse: 'Revision, Self-Assessment, AI Tutoring',
    isAccessibleForFree: true,
  }

  return (
    <div id="main" className="min-h-screen bg-nb text-nt font-sans">
      {/* Schema.org LearningResource */}
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{ __html: JSON.stringify(learningResourceJsonLd) }}
      />

      {/* Top Header */}
      <header className="sticky top-0 z-40 border-b border-bdr bg-nb/95 backdrop-blur-sm">
        <div className="mx-auto max-w-5xl px-4 sm:px-6 py-3 flex items-center justify-between gap-4">
          <Link to="/" className={`rounded-sm ${LINK_RING}`} aria-label="NorAI Home">
            <Wordmark size="md" />
          </Link>
          <div className="flex items-center gap-3">
            <Link
              to="/pricing"
              className={`hidden sm:inline-block text-14 text-nt2 hover:text-nt ${LINK_RING}`}
            >
              It's free
            </Link>
            <Button
              onClick={() => navigate(workspaceHref)}
              className="px-4 h-10 text-14 font-bold gap-1.5"
            >
              Open Workspace <ArrowRight size={15} />
            </Button>
          </div>
        </div>
      </header>

      {/* Hero Section */}
      <main className="mx-auto max-w-5xl px-4 sm:px-6 py-10 sm:py-16">
        {/* Breadcrumb & Metadata */}
        <div className="flex flex-wrap items-center gap-2 text-13 font-mono text-nt3 mb-6">
          <Link to="/" className="hover:text-nt transition-colors">
            NorAI
          </Link>
          <span>/</span>
          <Link to="/#demo" className="hover:text-nt transition-colors">
            Demo Lectures
          </Link>
          <span>/</span>
          <span className="text-nt font-medium">{data.badge}</span>
        </div>

        <div className="flex flex-col md:flex-row md:items-start justify-between gap-6 mb-8">
          <div className="flex-1">
            <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-ns2 text-12 font-medium text-nt2 border border-bdr mb-4">
              <span className="w-2 h-2 rounded-full bg-np" />
              <span>{data.institution}</span>
            </div>
            <h1 className="font-serif text-32 sm:text-44 font-bold text-nt leading-[1.1] tracking-tight mb-4 text-balance">
              {data.title}
            </h1>
            <p className="text-18 sm:text-20 text-nt2 leading-relaxed max-w-2xl font-serif italic">
              {data.headline}
            </p>
          </div>

          <div className="shrink-0 bg-ns border border-bdr rounded-lg p-5 w-full md:w-72 shadow-ev1">
            <div className="flex items-center justify-between gap-2 mb-3">
              <ShelfMark top={data.badge} time={data.duration} />
              <span className="text-12 font-mono text-nt3">{data.chapterCount} Chapters</span>
            </div>
            <div className="space-y-2 mb-5 text-13 text-nt2">
              <div className="flex items-center gap-2 text-nt">
                <BookOpen size={15} className="text-np" />
                <span>Study notes & formulas</span>
              </div>
              <div className="flex items-center gap-2 text-nt">
                <Check size={15} className="text-np" />
                <span>Key takeaways revision sheet</span>
              </div>
              <div className="flex items-center gap-2 text-nt">
                <Brain size={15} className="text-np" />
                <span>Spaced repetition flashcards</span>
              </div>
              <div className="flex items-center gap-2 text-nt">
                <Sparkles size={15} className="text-brass" />
                <span>AI Tutor Nora with citations</span>
              </div>
            </div>
            <Button
              onClick={() => navigate(workspaceHref)}
              className="w-full h-11 text-15 font-bold gap-2 justify-center"
            >
              Launch Workspace <ArrowRight size={16} />
            </Button>
          </div>
        </div>

        {/* Answer-First Executive Summary (Optimized for Search & AI Answer Engines) */}
        <section aria-labelledby="summary-heading" className="mb-14">
          <div className="bg-ns border-l-4 border-l-np border border-bdr rounded-r-lg p-6 sm:p-8 shadow-ev1">
            <div className="flex items-center gap-2 text-12 font-mono uppercase tracking-wider text-np font-bold mb-2">
              <Sparkles size={15} />
              <h2 id="summary-heading">Answer-First Lecture Overview</h2>
            </div>
            <p className="text-16 sm:text-17 leading-relaxed text-nt font-sans text-pretty">
              {data.answerSummary}
            </p>
          </div>
        </section>

        {/* Core Conceptual Takeaways Grid */}
        <section aria-labelledby="takeaways-heading" className="mb-14">
          <h2 id="takeaways-heading" className="font-serif text-24 sm:text-28 font-bold text-nt mb-2">
            Key Concepts & Definitions
          </h2>
          <p className="text-15 text-nt2 mb-6">
            Core definitions and theoretical principles formulated in this lecture.
          </p>
          <div className="grid gap-4 sm:grid-cols-2">
            {data.keyTakeaways.map((item) => (
              <div
                key={item.term}
                className="bg-ns border border-bdr rounded-lg p-5 hover:border-np/40 transition-colors"
              >
                <h3 className="font-serif font-bold text-17 text-nt mb-1.5 flex items-center gap-2">
                  <span className="w-1.5 h-1.5 rounded-full bg-np shrink-0" />
                  {item.term}
                </h3>
                <p className="text-14 text-nt2 leading-relaxed">{item.definition}</p>
              </div>
            ))}
          </div>
        </section>

        {/* Chapter Breakdown */}
        <section aria-labelledby="chapters-heading" className="mb-14">
          <div className="flex items-baseline justify-between gap-4 mb-2">
            <h2 id="chapters-heading" className="font-serif text-24 sm:text-28 font-bold text-nt">
              Chapter Breakdown & Syllabus
            </h2>
            <span className="text-13 font-mono text-nt3">{data.chapterCount} chapters total</span>
          </div>
          <p className="text-15 text-nt2 mb-6">
            Chronological outline in the exact order taught by the instructor.
          </p>

          <div className="border border-bdr rounded-lg bg-ns divide-y divide-bdr/60 overflow-hidden">
            {data.chapters.map((ch) => (
              <div key={ch.num} className="p-4 sm:p-5 flex flex-col sm:flex-row sm:items-start gap-4">
                <ShelfMark top={`CH ${ch.num}`} className="min-w-[58px] shrink-0" />
                <div className="flex-1 min-w-0">
                  <h3 className="font-serif font-bold text-16 sm:text-17 text-nt mb-1">
                    {ch.title}
                  </h3>
                  <p className="text-14 text-nt2 leading-relaxed">{ch.summary}</p>
                </div>
              </div>
            ))}
          </div>
        </section>

        {/* Sample Grounded AI Tutor Q&A */}
        <section aria-labelledby="tutor-heading" className="mb-14">
          <div className="flex items-center gap-2 text-12 font-mono uppercase tracking-wider text-brass font-bold mb-2">
            <Sparkles size={15} />
            <span>Nora AI Tutor Grounding</span>
          </div>
          <h2 id="tutor-heading" className="font-serif text-24 sm:text-28 font-bold text-nt mb-2">
            Sample Lecture-Grounded Questions
          </h2>
          <p className="text-15 text-nt2 mb-6">
            Nora answers directly from what the instructor said, citing the exact timestamp.
          </p>

          <div className="space-y-4">
            {data.sampleQa.map((qa) => (
              <div key={qa.question} className="bg-ns border border-bdr rounded-lg p-5 sm:p-6 shadow-ev1">
                <div className="flex items-start justify-between gap-3 mb-2.5">
                  <h3 className="font-serif font-bold text-16 text-nt leading-snug">
                    "{qa.question}"
                  </h3>
                  <span className="shrink-0 text-11 font-mono uppercase tracking-wider bg-np/10 text-np px-2 py-0.5 rounded border border-np/20">
                    {qa.source}
                  </span>
                </div>
                <p className="text-14 text-nt2 leading-relaxed mb-3">
                  {qa.answer}
                </p>
                <div className="text-12 font-mono text-nt3 flex items-center gap-1.5">
                  <span className="w-1.5 h-1.5 rounded-full bg-brass" />
                  Verified citation grounded in video transcript and slide keyframe
                </div>
              </div>
            ))}
          </div>
        </section>

        {/* Frequently Asked Questions */}
        <section aria-labelledby="faq-heading" className="mb-14">
          <div className="flex items-center gap-2 text-12 font-mono uppercase tracking-wider text-nt3 font-bold mb-2">
            <HelpCircle size={15} />
            <span>FAQ</span>
          </div>
          <h2 id="faq-heading" className="font-serif text-24 sm:text-28 font-bold text-nt mb-6">
            Frequently Asked Questions
          </h2>
          <div className="space-y-4">
            {data.faq.map((item) => (
              <div key={item.q} className="bg-ns border border-bdr rounded-lg p-5">
                <h3 className="font-serif font-bold text-16 text-nt mb-2">{item.q}</h3>
                <p className="text-14 text-nt2 leading-relaxed">{item.a}</p>
              </div>
            ))}
          </div>
        </section>

        {/* Final CTA Strip */}
        <section className="bg-npf text-npfg rounded-xl p-8 sm:p-12 text-center">
          <h2 className="font-serif text-26 sm:text-36 font-bold mb-3">
            Start Studying This Lecture in NorAI
          </h2>
          <p className="text-16 text-npfg/80 max-w-xl mx-auto mb-8 leading-relaxed">
            Access the complete study notes, practice with the 3-level quiz, review flashcards, or ask Nora any question. Free, no card required.
          </p>
          <div className="flex flex-col sm:flex-row items-center justify-center gap-4">
            <Button
              onClick={() => navigate(workspaceHref)}
              className="bg-brass text-[#16181A] hover:bg-brass/90 h-12 px-6 text-16 font-bold gap-2"
            >
              Open This Demo Workspace <ArrowRight size={17} />
            </Button>
            <Link
              to="/signup"
              className={`text-15 font-bold text-npfg underline decoration-2 underline-offset-4 hover:text-white ${LINK_RING}`}
            >
              Or create free account for your own lectures
            </Link>
          </div>
        </section>
      </main>
    </div>
  )
}
