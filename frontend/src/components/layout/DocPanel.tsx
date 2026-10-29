import { useState } from 'react'
import { useChapterStore } from '../../stores/useChapterStore'
import { Search, Download, Share2 } from 'lucide-react'
import { RevisionView } from '../doc/RevisionView'
import { NotesView } from '../doc/NotesView'
import { AssessmentView } from '../doc/AssessmentView'
import { StudyGuideView } from '../doc/StudyGuideView'
import { ConceptMapView } from '../doc/ConceptMapView'
import { SearchBar } from '../doc/SearchBar'
import { useToastStore } from '../../stores/useToastStore'
import { HighlightAsk } from '../doc/HighlightAsk'
import { VideoPlayer, VideoToggle } from '../video/VideoPlayer'
import { useLectureStore } from '../../stores/useLectureStore'
import { Button } from '../ui/Button'
import { SegmentedControl } from '../ui/SegmentedControl'
import { ShareModal } from '../doc/ShareModal'

type DocTab = 'notes' | 'revision' | 'assessment' | 'guide' | 'concepts'

// Zone colours (DESIGN.md): notes green, revision blue, quiz brick, guide
// violet, mind map brass. The active tab takes its zone's rule and tint.
const ZONES: { value: DocTab; label: string; dot: string; active: string }[] = [
  { value: 'notes', label: 'Study notes', dot: 'bg-z-notes', active: 'border-z-notes text-z-notes bg-z-notes/8' },
  { value: 'revision', label: 'Revision', dot: 'bg-z-revision', active: 'border-z-revision text-z-revision bg-z-revision/8' },
  { value: 'assessment', label: 'Quiz', dot: 'bg-z-quiz', active: 'border-z-quiz text-z-quiz bg-z-quiz/8' },
  { value: 'guide', label: 'Guide', dot: 'bg-z-cards', active: 'border-z-cards text-z-cards bg-z-cards/8' },
  { value: 'concepts', label: 'Mind map', dot: 'bg-brass', active: 'border-brass text-z-map bg-brass/10' },
]

const TOOL = 'gap-1.5 px-2 xl:px-2.5 h-8 min-w-8 rounded-md text-13 font-bold bg-transparent border-bdr2 text-nt2 hover:text-nt'

export function DocPanel() {
  const [searchOpen, setSearchOpen] = useState(false)
  const [shareOpen, setShareOpen] = useState(false)
  const activeDocTab = useChapterStore((s) => s.activeDocTab)
  const setDocTab = useChapterStore((s) => s.setDocTab)
  const activeChapterId = useChapterStore((s) => s.activeChapterId)
  const addToast = useToastStore((s) => s.addToast)
  const lectureId = useLectureStore(s => s.activeLectureId) || 'default'

  const handleDownloadPDF = () => {
    const pdfMap: Record<string, string> = {
      notes: 'study_notes',
      revision: 'revision',
      assessment: 'assessment',
      guide: 'guide',
      concepts: 'concepts',
    }
    const type = pdfMap[activeDocTab]
    if (type) {
      addToast('Opening print dialog…', 'info')
      window.open(`/print?type=${type}&lecture_id=${lectureId}`, '_blank')
    }
  }

  const handleDownloadInteractive = async () => {
    const { exportInteractiveMindmap } = await import('../../lib/exportInteractiveMindmap')
    try {
      await exportInteractiveMindmap(lectureId)
      addToast('Interactive mind map downloaded', 'success')
    } catch (err: unknown) {
      addToast(`Export failed: ${err instanceof Error ? err.message : 'unknown error'}`, 'error')
    }
  }

  return (
    <main className="relative flex flex-col min-w-0 min-h-0 border-r border-bdr bg-nb flex-1">
      {/* Mode bar: each study mode owns a zone colour */}
      <div className="flex items-stretch pl-2 pr-3 h-12 border-b border-bdr bg-ns gap-2 shrink-0 overflow-x-auto">
        <SegmentedControl
          containerClass="flex items-stretch shrink-0 whitespace-nowrap"
          itemClass="flex items-center gap-2 px-3 text-13 font-bold border-b-[3px] -mb-px transition-colors whitespace-nowrap cursor-pointer"
          inactiveClass="border-transparent text-nt3 hover:text-nt"
          options={ZONES.map((z) => ({
            value: z.value,
            label: z.label,
            prefix: <span aria-hidden="true" className={`w-2 h-2 rounded-[2px] ${z.dot}`} />,
            activeClass: z.active,
          }))}
          value={activeDocTab}
          onChange={(v) => setDocTab(v)}
        />

        <div className="ml-auto flex items-center gap-1.5 shrink-0">
          <VideoToggle />
          <Button
            variant="outline"
            onClick={() => setSearchOpen(!searchOpen)}
            aria-expanded={searchOpen}
            aria-label={searchOpen ? 'Close search' : 'Search the notes'}
            className={TOOL}
          >
            <Search size={14} strokeWidth={1.75} /> <span className="hidden xl:inline">{searchOpen ? 'Close search' : 'Search'}</span>
          </Button>

          <Button variant="outline" onClick={handleDownloadPDF} aria-label="Download as PDF" className={TOOL}>
            <Download size={14} strokeWidth={1.75} /> <span className="hidden xl:inline">PDF</span>
          </Button>

          <Button variant="outline" onClick={() => setShareOpen(true)} aria-label="Share this lecture" className={TOOL}>
            <Share2 size={14} strokeWidth={1.75} /> <span className="hidden xl:inline">Share</span>
          </Button>

          {activeDocTab === 'concepts' && (
            <Button variant="outline" onClick={handleDownloadInteractive} aria-label="Download the interactive mind map" className={TOOL}>
              <Download size={14} strokeWidth={1.75} /> <span className="hidden xl:inline">Interactive</span>
            </Button>
          )}

          {/* Inline search bar – only visible when search is open */}
          <SearchBar isOpen={searchOpen} onClose={() => setSearchOpen(false)} />
        </div>
      </div>

      {/* P6.3: collapsible YouTube player docked above the doc content */}
      <VideoPlayer />

      {/* Content */}
      {activeDocTab === 'concepts' ? (
        <ConceptMapView key={`concept-${activeChapterId}`} chapterId={activeChapterId} />
      ) : activeDocTab === 'guide' ? (
        <StudyGuideView />
      ) : activeDocTab === 'revision' ? (
        <RevisionView key={`rev-${activeChapterId}`} chapterId={activeChapterId} />
      ) : activeDocTab === 'notes' ? (
        <NotesView key={`notes-${activeChapterId}`} chapterId={activeChapterId} />
      ) : (
        <AssessmentView key={`assess-${activeChapterId}`} />
      )}
      {/* Highlight & Ask — floating button for text selection */}
      <HighlightAsk />
      <ShareModal lectureId={lectureId} isOpen={shareOpen} onClose={() => setShareOpen(false)} />
    </main>
  )
}