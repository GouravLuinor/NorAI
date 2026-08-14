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
import { VideoPlayer } from '../video/VideoPlayer'
import { useLectureStore } from '../../stores/useLectureStore'
import { Button } from '../ui/Button'
import { SegmentedControl } from '../ui/SegmentedControl'
import { ShareModal } from '../doc/ShareModal'

export function DocPanel() {
  const [searchOpen, setSearchOpen] = useState(false)
  const [shareOpen, setShareOpen] = useState(false)
  const { activeDocTab, setDocTab, activeChapterId } = useChapterStore()
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
      {/* Top bar */}
      <div className="flex items-center px-4 h-[38px] border-b border-bdr bg-ns gap-0.5 shrink-0 overflow-x-auto">
        <SegmentedControl
          containerClass="flex items-center gap-0.5 shrink-0 whitespace-nowrap"
          itemClass="px-2.5 py-1 rounded-sm text-11 transition whitespace-nowrap"
          options={[
            { value: 'notes', label: 'Study notes' },
            { value: 'revision', label: 'Revision' },
            { value: 'assessment', label: 'Assessment' },
            { value: 'guide', label: 'Guide' },
            { value: 'concepts', label: 'Mind map' },
          ]}
          value={activeDocTab}
          onChange={(v) => setDocTab(v)}
        />

        <div className="ml-auto flex items-center gap-1.5 shrink-0">
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

          <Button
            variant="outline"
            onClick={() => setShareOpen(true)}
            className="gap-1 px-2 py-1 rounded-sm text-2xs bg-transparent border-bdr2 active:translate-y-[1px] active:shadow-none"
          >
            <Share2 size={11} strokeWidth={1.5} /> Share
          </Button>

          {activeDocTab === 'concepts' && (
            <Button
              variant="outline"
              onClick={handleDownloadInteractive}
              className="gap-1 px-2 py-1 rounded-sm text-2xs bg-transparent border-bdr2 active:translate-y-[1px] active:shadow-none"
            >
              <Download size={11} strokeWidth={1.5} /> Interactive
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