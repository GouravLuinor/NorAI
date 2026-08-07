import { useState } from 'react'
import { useChapterStore } from '../../stores/useChapterStore'
import { Search, Download } from 'lucide-react'
import { RevisionView } from '../doc/RevisionView'
import { NotesView } from '../doc/NotesView'
import { AssessmentView } from '../doc/AssessmentView'
import { StudyGuideView } from '../doc/StudyGuideView'
import { ConceptMapView } from '../doc/ConceptMapView'
import { SearchBar } from '../doc/SearchBar'
import { useToastStore } from '../../stores/useToastStore'
import { HighlightAsk } from '../doc/HighlightAsk'
import { useLectureStore } from '../../stores/useLectureStore'
import { Button } from '../ui/Button'
import { SegmentedControl } from '../ui/SegmentedControl'

export function DocPanel() {
  const [searchOpen, setSearchOpen] = useState(false)
  const { activeDocTab, setDocTab, activeChapterId } = useChapterStore()
  const addToast = useToastStore((s) => s.addToast)
  const lectureId = useLectureStore(s => s.activeLectureId) || 'default'

  const handleDownloadPDF = () => {
    const pdfMap: Record<string, string> = {
      notes: 'study_notes',
      revision: 'revision',
      assessment: 'assessment',
      guide: 'revision',
      concepts: 'revision',
    }
    const type = pdfMap[activeDocTab]
    if (type) {
      addToast('Opening print dialog…', 'info')
      window.open(`/print?type=${type}&lecture_id=${lectureId}`, '_blank')
    }
  }

  return (
    <main className="flex flex-col min-w-0 min-h-0 border-r border-bdr bg-nb flex-1">
      {/* Top bar */}
      <div className="flex items-center px-4 h-[38px] border-b border-bdr bg-ns gap-0.5 shrink-0">
        <SegmentedControl
          options={[
            { value: 'notes', label: 'Study notes', prefix: <span className="font-mono text-3xs text-nt4 tracking-widest mr-1">03</span> },
            { value: 'revision', label: 'Revision', prefix: <span className="font-mono text-3xs text-nt4 tracking-widest mr-1">04</span> },
            { value: 'assessment', label: 'Assessment', prefix: <span className="font-mono text-3xs text-nt4 tracking-widest mr-1">05</span> },
            { value: 'guide', label: 'Guide', prefix: <span className="font-mono text-3xs text-nt4 tracking-widest mr-1">06</span> },
            { value: 'concepts', label: 'Mind map', prefix: <span className="font-mono text-3xs text-nt4 tracking-widest mr-1">07</span> },
          ]}
          value={activeDocTab}
          onChange={(v) => setDocTab(v)}
        />

        <div className="ml-auto flex items-center gap-1.5">
          {/* Search button – toggles the inline search bar */}
          <Button
            variant="outline"
            onClick={() => setSearchOpen(!searchOpen)}
            className="gap-1 px-2 py-1 rounded-sm text-2xs bg-transparent border-bdr2 active:translate-y-[1px] active:shadow-none"
          >
            <Search size={11} strokeWidth={1.5} /> {searchOpen ? 'Close' : 'Search'}
          </Button>

          <Button
            variant="outline"
            onClick={handleDownloadPDF}
            className="gap-1 px-2 py-1 rounded-sm text-2xs bg-transparent border-bdr2 active:translate-y-[1px] active:shadow-none"
          >
            <Download size={11} strokeWidth={1.5} /> PDF
          </Button>

          {/* Inline search bar – only visible when search is open */}
          <SearchBar isOpen={searchOpen} onClose={() => setSearchOpen(false)} />
        </div>
      </div>

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
    </main>
  )
}