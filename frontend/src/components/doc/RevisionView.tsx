import { chapter1Revision, type RevisionCard } from '../../mocks/revisionData'
import { Bookmark, GitBranch, FlaskConical, Clock, Lightbulb, AlertTriangle, Image } from 'lucide-react'

function DocCard({ card }: { card: RevisionCard }) {
  // Definition card — purple icon accent
  if (card.type === 'definition') {
    return (
      <div className="bg-ns border border-bdr2 rounded-lg p-4 mb-4 shadow-[0_1px_2px_rgba(0,0,0,0.28)]">
        <div className="flex items-center gap-1.5 text-[9.5px] font-semibold text-nt3 uppercase tracking-wider mb-2">
          <Bookmark size={13} className="text-np" />
          {card.title || 'Definition'}
        </div>
        <div className="text-[13px] font-medium text-nt mb-1">{card.term}</div>
        <div
          className="text-xs text-nt2 leading-relaxed"
          dangerouslySetInnerHTML={{ __html: card.description?.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>') || '' }}
        />
      </div>
    )
  }

  // Algorithm card — blue icon accent, numbered steps
  if (card.type === 'algorithm') {
    return (
      <div className="bg-ns border border-bdr2 rounded-lg p-4 mb-4 shadow-[0_1px_2px_rgba(0,0,0,0.28)]">
        <div className="flex items-center gap-1.5 text-[9.5px] font-semibold text-nt3 uppercase tracking-wider mb-2">
          <GitBranch size={13} className="text-nbl" />
          {card.title || 'Algorithm'}
        </div>
        <div className="text-[13px] font-medium text-nt mb-2">{card.term}</div>
        <ol className="list-none space-y-1 mt-2">
          {card.steps?.map((step, i) => (
            <li key={i} className="flex gap-2.5 text-xs text-nt2 leading-relaxed py-1">
              <span className="shrink-0 w-[18px] h-[18px] bg-ns2 rounded flex items-center justify-center text-[9px] font-semibold text-nt3 mt-0.5">
                {i + 1}
              </span>
              <span dangerouslySetInnerHTML={{ __html: step.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>').replace(/`(.*?)`/g, '<code class="font-mono text-[10px] bg-ns2 px-1 py-0.5 rounded text-nt border border-bdr">$1</code>').replace(/⌊/g, '⌊').replace(/⌋/g, '⌋') }} />
            </li>
          ))}
        </ol>
      </div>
    )
  }

  // Worked example card — amber icon accent
  if (card.type === 'example') {
    return (
      <div className="bg-ns border border-bdr2 rounded-lg p-4 mb-4 shadow-[0_1px_2px_rgba(0,0,0,0.28)]">
        <div className="flex items-center gap-1.5 text-[9.5px] font-semibold text-nt3 uppercase tracking-wider mb-2">
          <FlaskConical size={13} className="text-na" />
          {card.title || 'Worked Example'}
        </div>
        <div
          className="text-xs text-nt2 leading-relaxed"
          dangerouslySetInnerHTML={{ __html: card.description?.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>') || '' }}
        />
      </div>
    )
  }

  // Complexity card — green icon accent, data rows
  if (card.type === 'complexity') {
    return (
      <div className="bg-ns border border-bdr2 rounded-lg p-4 mb-4 shadow-[0_1px_2px_rgba(0,0,0,0.28)]">
        <div className="flex items-center gap-1.5 text-[9.5px] font-semibold text-nt3 uppercase tracking-wider mb-2">
          <Clock size={13} className="text-ng" />
          {card.title || 'Analysis'}
        </div>
        <div className="text-[13px] font-medium text-nt mb-1">{card.term}</div>
        <div className="mt-2">
          {card.rows?.map((row, i) => (
            <div
              key={i}
              className="flex items-center justify-between py-1.5 text-xs text-nt2 border-b border-bdr last:border-none last:pb-0"
            >
              <span>{row.label}</span>
              <span className="font-mono text-[11px] text-nt bg-ns2 px-1.5 py-0.5 rounded">
                {row.value}
              </span>
            </div>
          ))}
        </div>
      </div>
    )
  }

  // Hint callout — blue, compact
  if (card.type === 'hint') {
    return (
      <div className="flex gap-2.5 bg-ns2 rounded-lg p-3 mb-4 border border-bdr2">
        <Lightbulb size={14} className="text-nbl mt-0.5 shrink-0" />
        <div
          className="text-xs text-nt2 leading-relaxed"
          dangerouslySetInnerHTML={{ __html: card.description?.replace(/\*\*(.*?)\*\*/g, '<strong class="text-nt font-medium">$1</strong>') || '' }}
        />
      </div>
    )
  }

  // Mistake callout — red, compact
  if (card.type === 'mistake') {
    return (
      <div className="flex gap-2.5 bg-ns2 rounded-lg p-3 mb-4 border border-bdr2">
        <AlertTriangle size={14} className="text-nr mt-0.5 shrink-0" />
        <div
          className="text-xs text-nt2 leading-relaxed"
          dangerouslySetInnerHTML={{ __html: card.description?.replace(/\*\*(.*?)\*\*/g, '<strong class="text-nt font-medium">$1</strong>') || '' }}
        />
      </div>
    )
  }

  // Figure — screenshot placeholder
  if (card.type === 'figure') {
    return (
      <div className="my-5 rounded-lg overflow-hidden bg-ns border border-bdr2 cursor-zoom-in transition-colors hover:border-bdr">
        <div className="w-full aspect-video bg-gradient-to-br from-ns2 to-ns3 flex items-center justify-center text-nt4 text-2xl">
          <Image size={40} />
        </div>
        <div className="flex items-center justify-between px-3.5 py-2.5 text-[10px] text-nt3 border-t border-bdr">
          <span className="flex items-center gap-1">
            <Image size={12} /> {card.caption || 'Lecture slide'}
          </span>
        </div>
      </div>
    )
  }

  return null
}

export function RevisionView() {
  const chapter = chapter1Revision

  return (
    <div className="flex-1 overflow-y-auto px-8 py-7 pb-15 scroll-smooth doc-content">
      {/* Badge */}
      <div className="inline-flex items-center gap-1.5 px-2 py-1 rounded-md bg-ns2 border border-bdr2 text-[10px] text-nt3 mb-3.5">
        <span className="text-xs">📹</span> {chapter.lectureInfo}
      </div>

      {/* Title */}
      <h1 className="text-[21px] font-semibold text-nt tracking-tight mb-1 leading-tight">
        Ch {String(chapter.chapterId).padStart(2, '0')} — {chapter.title}
      </h1>

      {/* Meta */}
      <div className="text-[10.5px] text-nt3 mb-7 flex items-center gap-1.5">
        {chapter.lastEdited} <span className="w-0.5 h-0.5 rounded-full bg-nt4" /> {chapter.readTime}
      </div>

      {/* Sections */}
      {chapter.sections.map((section) => (
        <div key={section.anchor} id={section.anchor}>
          {/* Section heading */}
          <h2 className="text-[9.5px] font-semibold text-nt3 mb-3 mt-8 uppercase tracking-wider flex items-center gap-2 first:mt-0">
            {section.heading}
            <span className="flex-1 h-px bg-bdr" />
          </h2>

          {/* Paragraphs */}
          {section.paragraphs?.map((p, i) => (
            <p
              key={i}
              className="text-[12.5px] text-nt2 leading-relaxed mb-4 max-w-[560px]"
              dangerouslySetInnerHTML={{ __html: p.replace(/\*\*(.*?)\*\*/g, '<strong class="text-nt font-medium">$1</strong>').replace(/`(.*?)`/g, '<code class="font-mono text-[10px] bg-ns2 px-1.5 py-0.5 rounded text-nt border border-bdr">$1</code>') }}
            />
          ))}

          {/* Cards */}
          {section.cards?.map((card, i) => (
            <DocCard key={i} card={card} />
          ))}
        </div>
      ))}
    </div>
  )
}