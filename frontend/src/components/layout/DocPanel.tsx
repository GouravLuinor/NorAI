import { useState } from 'react'
import { useChapterStore } from '../../stores/useChapterStore'
import { Search, Download } from 'lucide-react'
import { RevisionView } from '../doc/RevisionView'
import { NotesView } from '../doc/NotesView'
import { AssessmentView } from '../doc/AssessmentView'
import { SearchBar } from '../doc/SearchBar'
import { useToastStore } from '../../stores/useToastStore'
import { HighlightAsk } from '../doc/HighlightAsk'


export function DocPanel() {
  const [searchOpen, setSearchOpen] = useState(false)
  const { activeDocTab, setDocTab, activeChapterId } = useChapterStore()
  const addToast = useToastStore((s) => s.addToast)

  console.log('DocPanel — activeChapterId:', activeChapterId)

  const handleDownloadPDF = () => {
    const pdfMap: Record<string, string> = {
      notes: 'study_notes',
      revision: 'revision',
      assessment: 'assessment',
    }
    const type = pdfMap[activeDocTab]
    if (type) {
      addToast('Downloading PDF…', 'info')
      window.open(`/download/${type}`, '_blank')
    }
  }

  return (
    <div className="flex flex-col min-w-0 min-h-0 border-r border-bdr bg-nb">
      {/* Top bar */}
      <div className="flex items-center px-4 h-[38px] border-b border-bdr bg-ns gap-0.5 shrink-0">
        {(['notes', 'revision', 'assessment'] as const).map((tab) => (
          <button
            key={tab}
            onClick={() => setDocTab(tab)}
            className={`px-2.5 py-1 rounded-md text-[11px] transition ${
              activeDocTab === tab
                ? 'text-nt bg-ns3'
                : 'text-nt3 hover:text-nt2'
            }`}
          >
            {tab === 'notes'
              ? 'Study notes'
              : tab === 'revision'
                ? 'Revision'
                : 'Assessment'}
          </button>
        ))}

        <div className="ml-auto flex items-center gap-1.5">
          {/* Search button – toggles the inline search bar */}
          <button
            onClick={() => setSearchOpen(!searchOpen)}
            className="flex items-center gap-1 px-2 py-1 rounded-md border border-bdr2 bg-transparent text-nt3 text-[10px] hover:bg-ns2 hover:text-nt2 transition active:scale-98"
          >
            <Search size={11} /> {searchOpen ? 'Close' : 'Search'}
          </button>

          <button
            onClick={handleDownloadPDF}
            className="flex items-center gap-1 px-2 py-1 rounded-md border border-bdr2 bg-transparent text-nt3 text-[10px] hover:bg-ns2 hover:text-nt2 transition active:scale-98"
          >
            <Download size={11} /> PDF
          </button>

          {/* Inline search bar – only visible when search is open */}
          <SearchBar isOpen={searchOpen} onClose={() => setSearchOpen(false)} />
        </div>
      </div>

      {/* Content */}
      {activeDocTab === 'revision' ? (
        <RevisionView key={`rev-${activeChapterId}`} chapterId={activeChapterId} />
      ) : activeDocTab === 'notes' ? (
        <NotesView key={`notes-${activeChapterId}`} chapterId={activeChapterId} />
      ) : (
        <AssessmentView key={`assess-${activeChapterId}`} />
      )}
      {/* Highlight & Ask — floating button for text selection */}
      <HighlightAsk />
    </div>
  )
}