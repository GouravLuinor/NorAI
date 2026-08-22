import { useState, type KeyboardEvent } from 'react'
import { motion } from 'framer-motion'
import { Sparkles, ArrowRight, Play, Check, BookOpen, Layers, FileText, Brain, Video, ShieldCheck, Zap, ChevronRight, GitFork, Menu, X } from 'lucide-react'
import { Link } from 'react-router-dom'
import { useAuthStore } from '../stores/useAuthStore'

interface LandingPageProps {
  onStartWorkspace: () => void
}

const TABS = [
  { id: 'notes', label: '01 Study Notes' },
  { id: 'tutor', label: '02 AI Tutor (RAG)' },
  { id: 'quiz', label: '03 Assessments' },
  { id: 'mindmap', label: '04 Mind Map' },
] as const
type TabId = (typeof TABS)[number]['id']

export function LandingPage({ onStartWorkspace }: LandingPageProps) {
  const user = useAuthStore((s) => s.user)
  const openAuthModal = useAuthStore((s) => s.openAuthModal)
  const [activeTab, setActiveTab] = useState<TabId>('notes')
  const [mobileOpen, setMobileOpen] = useState(false)

  const handleTabKeyDown = (e: KeyboardEvent<HTMLDivElement>) => {
    const ids = TABS.map((t) => t.id)
    const idx = ids.indexOf(activeTab)
    let next: TabId | null = null
    if (e.key === 'ArrowRight') next = ids[(idx + 1) % ids.length]
    else if (e.key === 'ArrowLeft') next = ids[(idx - 1 + ids.length) % ids.length]
    else if (e.key === 'Home') next = ids[0]
    else if (e.key === 'End') next = ids[ids.length - 1]
    if (next) {
      e.preventDefault()
      setActiveTab(next)
      document.getElementById(`wp-tab-${next}`)?.focus()
    }
  }

  const handleCTA = () => {
    if (!user) {
      openAuthModal('signup')
    } else {
      onStartWorkspace()
    }
  }

  return (
    <div id="main" className="min-h-screen bg-nb text-nt font-sans selection:bg-npb selection:text-npt flex flex-col relative overflow-x-hidden">
      {/* Blueprint grid background effect */}
      <div
        aria-hidden="true"
        className="absolute inset-0 pointer-events-none opacity-40 z-0"
        style={{
          backgroundImage: `linear-gradient(to right, var(--color-grid) 1px, transparent 1px), linear-gradient(to bottom, var(--color-grid) 1px, transparent 1px)`,
          backgroundSize: '32px 32px'
        }}
      />

      {/* Header Bar */}
      <header className="sticky top-0 z-40 bg-nb/90 backdrop-blur-md border-b border-bdr px-6 py-3.5">
        <div className="max-w-7xl mx-auto flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 rounded-md bg-np text-npfg font-serif font-bold text-18 flex items-center justify-center shadow-bp">
              N
            </div>
            <div className="flex flex-col">
              <span className="font-serif font-bold text-18 tracking-tight text-nt leading-none">NorAI</span>
              <span className="text-3xs font-mono tracking-wider text-nt3 uppercase">Sketchbook Edition</span>
            </div>
          </div>

          <nav className="hidden md:flex items-center gap-6 font-display text-11 uppercase tracking-wider text-nt2 font-medium">
            <a href="#features" className="hover:text-nt transition-colors">Features</a>
            <a href="#how-it-works" className="hover:text-nt transition-colors">How It Works</a>
            <Link to="/pricing" className="hover:text-nt transition-colors">Pricing</Link>
          </nav>

          <div className="flex items-center gap-3">
            {user ? (
              <button
                onClick={onStartWorkspace}
                className="bg-np hover:bg-nph text-npfg font-display text-11 font-semibold uppercase tracking-wider px-4 py-2 rounded-md shadow-bp flex items-center gap-1.5 cursor-pointer transition-[background-color,transform] active:translate-y-0.5"
              >
                <span>Workspace</span>
                <ArrowRight size={13} />
              </button>
            ) : (
              <>
                <button
                  onClick={() => openAuthModal('login')}
                  className="text-nt2 hover:text-nt font-display text-11 font-medium uppercase tracking-wider px-3 py-1.5 transition-colors cursor-pointer"
                >
                  Log In
                </button>
                <button
                  onClick={() => openAuthModal('signup')}
                  className="bg-np hover:bg-nph text-npfg font-display text-11 font-semibold uppercase tracking-wider px-4 py-2 rounded-md shadow-bp flex items-center gap-1.5 cursor-pointer transition-[background-color,transform] active:translate-y-0.5"
                >
                  <span>Start Free Trial</span>
                </button>
              </>
            )}

            <button
              onClick={() => setMobileOpen((o) => !o)}
              className="md:hidden p-2 -mr-1 rounded-md text-nt2 hover:text-nt hover:bg-ns2 transition-colors cursor-pointer"
              aria-label={mobileOpen ? 'Close navigation menu' : 'Open navigation menu'}
              aria-expanded={mobileOpen}
            >
              {mobileOpen ? <X size={18} /> : <Menu size={18} />}
            </button>
          </div>
        </div>

        {mobileOpen && (
          <div className="md:hidden bg-ns border-t border-bdr px-6 py-4 flex flex-col gap-3 font-display text-11 uppercase tracking-wider text-nt2 font-medium">
            <a href="#features" onClick={() => setMobileOpen(false)} className="hover:text-nt transition-colors">Features</a>
            <a href="#how-it-works" onClick={() => setMobileOpen(false)} className="hover:text-nt transition-colors">How It Works</a>
            <Link to="/pricing" onClick={() => setMobileOpen(false)} className="hover:text-nt transition-colors">Pricing</Link>
          </div>
        )}
      </header>

      {/* Hero Section */}
      <section className="relative z-10 pt-16 pb-20 px-6 max-w-6xl mx-auto text-center">
        <motion.div
          initial={{ opacity: 0, y: -10 }}
          animate={{ opacity: 1, y: 0 }}
          className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-npb border border-npbr text-npt font-mono text-11 font-medium mb-6"
        >
          <Sparkles size={12} className="text-np" />
          <span>LECTURE VIDEO → EXAM-READY STUDY SUITE</span>
        </motion.div>

        <h1 className="font-serif text-4xl sm:text-6xl text-nt font-normal tracking-tight leading-[1.1] mb-6 max-w-4xl mx-auto text-balance">
          Turn Long Lectures Into <br />
          <span className="italic text-np font-serif">High-Grade Study Notes</span> & AI Tutor
        </h1>

        <p className="font-sans text-nt2 text-15 sm:text-17 max-w-2xl mx-auto mb-9 font-normal leading-relaxed">
          Drop in a YouTube URL or lecture video. NorAI builds chapter study notes, revision cheat-sheets, 3D flashcards, quizzes, and a lecture-grounded AI tutor.
        </p>

        <div className="flex flex-col sm:flex-row items-center justify-center gap-4 mb-14">
          <button
            onClick={handleCTA}
            className="w-full sm:w-auto bg-np hover:bg-nph text-npfg font-display text-12 font-semibold uppercase tracking-wider px-7 py-3.5 rounded-md shadow-bp flex items-center justify-center gap-2 cursor-pointer transition-[background-color,transform,box-shadow] hover:-translate-y-0.5 active:translate-y-0 active:shadow-none"
          >
            <span>Try 1 Video Free (No Card)</span>
            <ArrowRight size={16} />
          </button>

          <button
            onClick={onStartWorkspace}
            className="w-full sm:w-auto bg-ns hover:bg-ns2 border border-bdr text-nt font-display text-12 font-medium uppercase tracking-wider px-6 py-3.5 rounded-md shadow-ev1 flex items-center justify-center gap-2 cursor-pointer transition-colors"
          >
            <Play size={14} className="text-np fill-np" />
            <span>Launch Live Workspace</span>
          </button>
        </div>

        {/* Micro Trust Indicators */}
        <div className="flex flex-wrap items-center justify-center gap-6 font-mono text-11 text-nt3 border-t border-bdr pt-6 max-w-3xl mx-auto">
          <span className="flex items-center gap-1.5">
            <Check size={14} className="text-ng" /> 100% Free 1-Video Trial
          </span>
          <span className="flex items-center gap-1.5">
            <Check size={14} className="text-ng" /> Gemini 3.1 Flash Grounded
          </span>
          <span className="flex items-center gap-1.5">
            <Check size={14} className="text-ng" /> KaTeX Math + Timestamped Citations
          </span>
        </div>
      </section>

      {/* Interactive Mockup Workspace Preview */}
      <section className="relative z-10 px-6 mb-24 max-w-5xl mx-auto w-full">
        <div className="bg-ns border border-bdr rounded-lg shadow-bp overflow-hidden">
          {/* Mockup Header */}
          <div className="bg-ns2 border-b border-bdr px-4 py-2.5 flex items-center justify-between gap-2">
            <div className="flex items-center gap-2 min-w-0">
              <span className="w-2.5 h-2.5 rounded-full bg-nr opacity-80 shrink-0" />
              <span className="w-2.5 h-2.5 rounded-full bg-na opacity-80 shrink-0" />
              <span className="w-2.5 h-2.5 rounded-full bg-ng opacity-80 shrink-0" />
              <span className="font-mono text-11 text-nt3 ml-2 font-medium truncate">NorAI Workspace — MIT 8.01 Physics Lecture 04</span>
            </div>
            <div className="flex items-center gap-2 shrink-0 hidden sm:flex">
              <span className="px-2 py-0.5 rounded bg-ngb text-ngt font-mono text-3xs font-medium uppercase">Processing Complete</span>
            </div>
          </div>

          {/* Workspace Tabs Bar */}
          <div
            role="tablist"
            aria-label="Workspace preview"
            onKeyDown={handleTabKeyDown}
            className="bg-ns3 border-b border-bdr px-4 py-2 flex items-center gap-2 overflow-x-auto font-display text-11 uppercase font-medium text-nt2"
          >
            {TABS.map((tab) => (
              <button
                key={tab.id}
                id={`wp-tab-${tab.id}`}
                role="tab"
                aria-selected={activeTab === tab.id}
                aria-controls="wp-panel"
                tabIndex={activeTab === tab.id ? 0 : -1}
                onClick={() => setActiveTab(tab.id)}
                className={`px-3 py-1 rounded whitespace-nowrap transition-colors ${activeTab === tab.id ? 'bg-ns text-np font-bold shadow-xs' : 'hover:text-nt'}`}
              >
                {tab.label}
              </button>
            ))}
          </div>

          {/* Interactive Mockup Body */}
          <div
            id="wp-panel"
            role="tabpanel"
            aria-labelledby={`wp-tab-${activeTab}`}
            className="p-6 min-h-[320px] font-sans text-13"
          >
            {activeTab === 'notes' && (
              <div className="space-y-4">
                <div className="border-b border-bdr pb-2">
                  <span className="font-mono text-11 text-np uppercase tracking-wider font-semibold">Chapter 02 — Work-Energy Theorem</span>
                  <h3 className="font-serif text-22 text-nt font-normal mt-1">Kinetic Energy & Mathematical Derivation</h3>
                </div>
                <p className="text-nt2 leading-relaxed">
                  The net work done on an object by external forces equals the change in its kinetic energy:
                </p>
                <div className="p-3 bg-ns2 border border-bdr rounded font-mono text-10 sm:text-12 text-nt text-center my-3 overflow-x-auto">
                  W_net = \Delta K = \frac&#123;1&#125;&#123;2&#125; m v_f^2 - \frac&#123;1&#125;&#123;2&#125; m v_i^2
                </div>
                <div className="flex items-center gap-3 p-2 bg-npb border border-npbr rounded text-11 text-npt">
                  <span className="font-mono font-bold bg-np text-npfg px-1.5 py-0.5 rounded text-3xs">[08:45]</span>
                  <span>Professor derives integral of force over displacement on the blackboard.</span>
                </div>
              </div>
            )}

            {activeTab === 'tutor' && (
              <div className="space-y-3">
                <div className="p-3 bg-ns2 border border-bdr rounded-lg text-nt2 text-12 max-w-lg ml-auto">
                  How is conservative force defined in this lecture?
                </div>
                <div className="p-3.5 bg-ns border border-bdr rounded-lg text-nt text-12 max-w-xl space-y-2">
                  <div className="flex items-center justify-between border-b border-bdr pb-1 text-10 font-mono text-nt3">
                    <span className="font-bold text-np">Nora (Socratic Tutor)</span>
                    <span className="px-1.5 py-0.5 bg-nblb text-nblt rounded">References (3)</span>
                  </div>
                  <p>
                    A force is conservative if the work done in moving an object between two points is independent of the path taken.
                  </p>
                  <div className="text-11 text-nt3 italic bg-ns2 p-2 rounded border border-bdr">
                    "Notice at 14:20 how gravity satisfies this property because the closed loop integral ∮ F · dr = 0."
                  </div>
                </div>
              </div>
            )}

            {activeTab === 'quiz' && (
              <div className="space-y-4 max-w-lg mx-auto">
                <div className="font-mono text-11 text-nt3 flex justify-between">
                  <span>Question 2 of 8</span>
                  <span className="text-na font-semibold">Medium Difficulty</span>
                </div>
                <h4 className="font-serif text-16 text-nt font-normal">
                  If the velocity of an object is doubled, by what factor does its kinetic energy increase?
                </h4>
                <div className="space-y-2">
                  {['Factor of 2', 'Factor of 4 (Correct)', 'Factor of 8', 'Remains unchanged'].map((opt, i) => (
                    <div
                      key={i}
                      className={`p-2.5 rounded border text-12 font-medium ${
                        i === 1 ? 'bg-ngb border-ngbr text-ngt font-bold' : 'bg-ns2 border-bdr text-nt2'
                      }`}
                    >
                      {String.fromCharCode(65 + i)}. {opt}
                    </div>
                  ))}
                </div>
              </div>
            )}

            {activeTab === 'mindmap' && (
              <div className="flex flex-col items-center justify-center p-6 border border-dashed border-bdr rounded bg-ns2">
                <div className="font-mono text-11 text-np font-bold mb-2">3-Tier Hierarchical Concept Graph</div>
                <div className="flex items-center gap-4 text-11 font-mono text-nt2">
                  <span className="p-2 bg-ns border border-bdr rounded font-bold">Classical Mechanics</span>
                  <ChevronRight size={14} />
                  <span className="p-2 bg-npb border border-npbr text-npt rounded font-bold">Work & Energy</span>
                  <ChevronRight size={14} />
                  <span className="p-2 bg-ns border border-bdr rounded">Kinetic Theorem</span>
                </div>
              </div>
            )}
          </div>
        </div>
      </section>

      {/* Interactive Live Demo Workspaces */}
      <section className="relative z-10 py-16 px-6 max-w-6xl mx-auto w-full">
        <div className="text-center mb-12">
          <div className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full bg-npb border border-npbr text-npt font-mono text-11 font-medium mb-3">
            <Sparkles size={12} className="text-np" />
            <span>NO SIGNUP OR PAYMENT REQUIRED</span>
          </div>
          <h2 className="font-serif text-3xl sm:text-4xl text-nt font-normal tracking-tight text-balance">
            Explore 3 Live Demo Workspaces
          </h2>
          <p className="text-nt2 text-14 max-w-xl mx-auto mt-2 font-normal">
            Click any workspace below to experience full study notes, interactive quizzes, flashcards, and Nora AI Tutor.
          </p>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          {[
            {
              id: 'ab648382-638f-4dde-b7c1-4007a2e638bb',
              category: 'Computer Science & Deep Learning',
              title: 'Foundations of Neural Networks & Deep Learning',
              chapters: '4 Chapters',
              duration: '18 min video',
              badge: 'Deep Learning',
              desc: 'Mathematical parameterization, activation functions comparison (Sigmoid vs ReLU), and matrix transformations.',
            },
            {
              id: 'e54d7376-0e7b-472a-9ca6-9b21ad0b2710',
              category: 'Economics & Market Theory',
              title: 'Foundations of Economic Thinking: Incentives & Opportunity Cost',
              chapters: '6 Chapters',
              duration: '19 min video',
              badge: 'Economics',
              desc: 'Market coordination, supply-demand distortions under price ceilings & floors, and capital flight economics.',
            },
            {
              id: '506dd685-05f9-43df-8d09-5b944c7392f5',
              category: 'Modern AI Engineering',
              title: 'The Rise of Open-Weights Models and Local Deployment',
              chapters: '3 Chapters',
              duration: '10 min video',
              badge: 'AI Systems',
              desc: 'Memory requirements for local LLM inference, 4-bit VRAM calculations, and dynamic quantization efficiencies.',
            },
          ].map((demo) => (
            <Link
              key={demo.id}
              to={`/workspace/${demo.id}`}
              className="group bg-ns hover:bg-ns2 border border-bdr hover:border-npbr rounded-lg p-6 shadow-bp transition-all duration-200 flex flex-col justify-between cursor-pointer hover:-translate-y-1"
            >
              <div>
                <div className="flex items-center justify-between gap-2 mb-3">
                  <span className="font-mono text-10 font-bold uppercase tracking-wider text-np bg-npb px-2 py-0.5 rounded border border-npbr">
                    {demo.badge}
                  </span>
                  <span className="font-mono text-11 text-nt3">
                    {demo.duration}
                  </span>
                </div>

                <h3 className="font-serif text-18 text-nt font-normal group-hover:text-np transition-colors leading-snug mb-2">
                  {demo.title}
                </h3>

                <p className="font-sans text-12 text-nt2 leading-relaxed mb-4">
                  {demo.desc}
                </p>
              </div>

              <div className="pt-4 border-t border-bdr flex items-center justify-between text-11 font-display uppercase tracking-wider text-nt2 font-semibold group-hover:text-np">
                <span className="font-mono text-10 text-nt3 lowercase">{demo.chapters}</span>
                <span className="flex items-center gap-1">
                  Launch Demo <ArrowRight size={13} className="transition-transform group-hover:translate-x-1" />
                </span>
              </div>
            </Link>
          ))}
        </div>
      </section>

      {/* How It Works (Blueprint Stepper 01-04) */}
      <section id="how-it-works" className="relative z-10 py-20 px-6 bg-ns border-y border-bdr">
        <div className="max-w-6xl mx-auto">
          <div className="text-center mb-16">
            <span className="font-mono text-11 text-np uppercase tracking-wider font-semibold">Pipeline Architecture</span>
            <h2 className="font-serif text-3xl sm:text-4xl text-nt font-normal mt-1 text-balance">Four Steps From Video to Mastery</h2>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-4 gap-6">
            {[
              {
                num: '01',
                title: 'Media Ingest',
                desc: 'Paste YouTube URLs, Google Drive files, or local MP4/MP3 recordings.',
                icon: Video,
              },
              {
                num: '02',
                title: '18-Stage Pipeline',
                desc: 'Whisper audio transcription, frame extraction, scene change detection.',
                icon: Zap,
              },
              {
                num: '03',
                title: 'Artifact Synthesis',
                desc: 'Gemini 3.1 Flash builds structured study notes, revision sheets, & 3D cards.',
                icon: FileText,
              },
              {
                num: '04',
                title: 'Socratic Tutor',
                desc: 'Ask questions with exact timestamp citations and chapter-aware guidance.',
                icon: Brain,
              },
            ].map((item, idx) => (
              <div key={idx} className="bg-nb border border-bdr p-6 rounded-md shadow-bp relative">
                <div className="font-serif text-28 text-np font-bold mb-3">{item.num}</div>
                <h3 className="font-serif text-18 text-nt font-normal mb-2">{item.title}</h3>
                <p className="font-sans text-12 text-nt2 leading-relaxed">{item.desc}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Features Grid */}
      <section id="features" className="relative z-10 py-20 px-6 max-w-6xl mx-auto">
        <div className="text-center mb-16">
            <span className="font-mono text-11 text-np uppercase tracking-wider font-semibold">Architect's Feature Suite</span>
            <h2 className="font-serif text-3xl sm:text-4xl text-nt font-normal mt-1 text-balance">Everything Needed for Academic Excellence</h2>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          <div className="bg-ns border border-bdr p-6 rounded-md shadow-ev1">
            <BookOpen size={24} className="text-np mb-3" />
            <h3 className="font-serif text-18 text-nt font-normal mb-2">Chapter Study Notes</h3>
            <p className="font-sans text-12 text-nt2 leading-relaxed">
              Hierarchical markdown notes formatted with KaTeX math expressions, key terms, and visual screenshot thumbnails.
            </p>
          </div>

          <div className="bg-ns border border-bdr p-6 rounded-md shadow-ev1">
            <Layers size={24} className="text-np mb-3" />
            <h3 className="font-serif text-18 text-nt font-normal mb-2">Revision Cheat-Sheets</h3>
            <p className="font-sans text-12 text-nt2 leading-relaxed">
              Condensed quick-scan revision cheat-sheets paired with print-ready PDF export functionality.
            </p>
          </div>

          <div className="bg-ns border border-bdr p-6 rounded-md shadow-ev1">
            <Brain size={24} className="text-np mb-3" />
            <h3 className="font-serif text-18 text-nt font-normal mb-2">Grounded AI Tutor</h3>
            <p className="font-sans text-12 text-nt2 leading-relaxed">
              RAG tutor using LangGraph checkpoints, timestamp citations, Socratic mode, and custom persona prompts.
            </p>
          </div>

          <div className="bg-ns border border-bdr p-6 rounded-md shadow-ev1">
            <GitFork size={24} className="text-np mb-3" />
            <h3 className="font-serif text-18 text-nt font-normal mb-2">Hierarchical Mind Maps</h3>
            <p className="font-sans text-12 text-nt2 leading-relaxed">
              Interactive 3-tier concept graphs generated zero-LLM with draggable nodes and floatable details cards.
            </p>
          </div>

          <div className="bg-ns border border-bdr p-6 rounded-md shadow-ev1">
            <Zap size={24} className="text-np mb-3" />
            <h3 className="font-serif text-18 text-nt font-normal mb-2">Quiz & Flashcard History</h3>
            <p className="font-sans text-12 text-nt2 leading-relaxed">
              Persisted attempt histories, rating stats, SHA-256 deck keying, and "Retake Missed Only" filters.
            </p>
          </div>

          <div className="bg-ns border border-bdr p-6 rounded-md shadow-ev1">
            <ShieldCheck size={24} className="text-np mb-3" />
            <h3 className="font-serif text-18 text-nt font-normal mb-2">Per-Lecture Isolation</h3>
            <p className="font-sans text-12 text-nt2 leading-relaxed">
              Dedicated Chroma vector databases, SQLite thread checkpoints, and outputs directories for every lecture.
            </p>
          </div>
        </div>
      </section>

      {/* Footer */}
      <footer className="relative z-10 bg-ns border-t border-bdr py-8 px-6 text-11 font-sans text-nt3">
        <div className="max-w-7xl mx-auto flex flex-col sm:flex-row items-center justify-between gap-4">
          <div className="flex items-center gap-2">
            <span className="w-5 h-5 rounded bg-np text-npfg font-serif font-bold text-11 flex items-center justify-center">N</span>
            <span className="font-serif font-bold text-nt text-13">NorAI</span>
            <span>© 2026 NorAI Inc. All rights reserved.</span>
          </div>
          <div className="flex items-center gap-6 font-display uppercase tracking-wider">
            <Link to="/pricing" className="hover:text-nt transition-colors">Pricing</Link>
          </div>
        </div>
      </footer>
    </div>
  )
}
