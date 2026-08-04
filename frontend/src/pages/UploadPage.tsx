import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { Sparkles, Film, Upload, Link2, FileVideo, ArrowRight, BookOpen, Clock } from 'lucide-react'

type InputType = 'youtube' | 'upload' | 'drive'

interface LectureInfo {
  lecture_id: string
  title: string
  created_at: string
  chapter_count: number
}

// Simple helper to convert an ISO date string to a relative time format
function getRelativeTime(dateString: string) {
  const date = new Date(dateString)
  const now = new Date()
  const diffInSeconds = Math.floor((now.getTime() - date.getTime()) / 1000)

  if (diffInSeconds < 60) return 'Just now'
  if (diffInSeconds < 3600) return `${Math.floor(diffInSeconds / 60)} minutes ago`
  if (diffInSeconds < 86400) return `${Math.floor(diffInSeconds / 3600)} hours ago`
  return `${Math.floor(diffInSeconds / 86400)} days ago`
}

export function UploadPage() {
  const [inputType, setInputType] = useState<InputType>('youtube')
  const [url, setUrl] = useState('')
  const [file, setFile] = useState<File | null>(null)
  const [lectures, setLectures] = useState<LectureInfo[]>([])
  const [loadingLectures, setLoadingLectures] = useState(true)
  const navigate = useNavigate()

  useEffect(() => {
    fetch('/lectures')
      .then((res) => res.json())
      .then((data: LectureInfo[]) => {
        setLectures(data.slice(0, 5)) // Take max 5 most recent
        setLoadingLectures(false)
      })
      .catch((err) => {
        console.error('Failed to fetch lectures:', err)
        setLoadingLectures(false)
      })
  }, [])

  const handleStart = async () => {
    const formData = new FormData()
    formData.append('source_type', inputType)
    if (inputType === 'upload' && file) {
      formData.append('file', file)
    } else {
      formData.append('url', url)
    }

    const res = await fetch('/process', { method: 'POST', body: formData })
    const { task_id } = await res.json()
    navigate(`/process/${task_id}`)
  }

  const canSubmit =
    (inputType === 'upload' && file) ||
    ((inputType === 'youtube' || inputType === 'drive') && url.trim())

  return (
    <div className="min-h-screen bg-nb flex flex-col items-center py-12 px-6">
      <div className="w-full max-w-lg flex flex-col gap-10">
        
        {/* ───────────────────────────────────────────────────────────────── */}
        {/* Section 1: Upload (Top)                                           */}
        {/* ───────────────────────────────────────────────────────────────── */}
        <section>
          {/* Logo & Tagline */}
          <div className="text-center mb-8">
            <div className="flex items-center justify-center gap-2 mb-3">
              <div className="w-10 h-10 rounded-lg bg-np flex items-center justify-center text-lg font-semibold text-npfg shadow-ev2">
                N
              </div>
              <span className="text-2xl font-semibold text-nt tracking-tight">
                NorAI
              </span>
            </div>
            <p className="text-sm text-nt2 max-w-sm mx-auto leading-relaxed">
              Transform your lecture into a complete study experience with AI.
            </p>
          </div>

          {/* Input Card */}
          <div className="bg-ns border border-bdr2 rounded-xl p-5 shadow-ev3">
            {/* Segmented Control */}
            <div className="flex bg-nb rounded-lg p-1 mb-4">
              {([
                ['youtube', Film, 'YouTube'],
                ['upload', Upload, 'Upload'],
                ['drive', Link2, 'Drive'],
              ] as const).map(([type, Icon, label]) => (
                <button
                  key={type}
                  onClick={() => setInputType(type)}
                  className={`flex-1 flex items-center justify-center gap-2 py-2 rounded-md text-xs font-medium transition ${
                    inputType === type
                      ? 'bg-ns3 text-nt shadow-ev1'
                      : 'text-nt3 hover:text-nt2'
                  }`}
                >
                  <Icon size={14} />
                  {label}
                </button>
              ))}
            </div>

            {/* Input Area */}
            {inputType === 'upload' ? (
              <label className="flex flex-col items-center justify-center gap-3 p-8 border-2 border-dashed border-bdr2 rounded-lg cursor-pointer hover:border-np transition">
                <FileVideo size={28} className="text-nt3" />
                <span className="text-xs text-nt2">
                  {file ? file.name : 'Click or drag a video file here'}
                </span>
                <span className="text-2xs text-nt4">MP4, MKV, WebM up to 2 GB</span>
                <input
                  type="file"
                  accept="video/*"
                  className="hidden"
                  onChange={(e) => setFile(e.target.files?.[0] ?? null)}
                />
              </label>
            ) : (
              <div className="relative">
                <input
                  type="text"
                  value={url}
                  onChange={(e) => setUrl(e.target.value)}
                  placeholder={
                    inputType === 'youtube'
                      ? 'Paste YouTube URL…'
                      : 'Paste Google Drive share link…'
                  }
                  className="w-full bg-nb border border-bdr2 rounded-lg px-4 py-2.5 pr-12 text-13 text-nt placeholder:text-nt4 outline-none focus:border-np transition"
                />
                <div className="absolute right-3 top-1/2 -translate-y-1/2 text-nt3">
                  {inputType === 'youtube' ? <Film size={15} /> : <Link2 size={15} />}
                </div>
              </div>
            )}

            {/* Submit Button */}
            <button
              onClick={handleStart}
              disabled={!canSubmit}
              className="w-full mt-4 flex items-center justify-center gap-2 py-2.5 rounded-lg bg-np text-npfg text-13 font-medium shadow-ev2 hover:bg-nph transition disabled:opacity-40 disabled:cursor-not-allowed"
            >
              <Sparkles size={14} />
              Start Processing
            </button>
          </div>

          <p className="text-center text-2xs text-nt4 mt-4">
            ⓘ Works with lectures up to 3 hours. We'll generate notes, quizzes & more.
          </p>
        </section>


        {/* ───────────────────────────────────────────────────────────────── */}
        {/* Divider                                                           */}
        {/* ───────────────────────────────────────────────────────────────── */}
        <div className="flex items-center gap-4 px-2">
          <div className="flex-1 h-px bg-bdr2" />
          <div className="text-2xs font-medium text-nt4 uppercase tracking-widest">
            Or
          </div>
          <div className="flex-1 h-px bg-bdr2" />
        </div>


        {/* ───────────────────────────────────────────────────────────────── */}
        {/* Section 2: Your Lectures (Bottom)                                 */}
        {/* ───────────────────────────────────────────────────────────────── */}
        <section>
          <h2 className="text-13 font-medium text-nt mb-4 px-1">Your Recent Lectures</h2>
          
          <div className="flex flex-col gap-2.5">
            {loadingLectures ? (
              <div className="flex justify-center p-6 text-nt4">
                <span className="animate-pulse text-xs">Loading...</span>
              </div>
            ) : lectures.length === 0 ? (
              <div className="bg-ns border border-bdr2 rounded-xl p-8 text-center shadow-ev2">
                <BookOpen size={24} className="mx-auto text-nt4 mb-3" />
                <h3 className="text-xs font-medium text-nt2 mb-1">No lectures yet</h3>
                <p className="text-11 text-nt4">Your processed lectures will appear here</p>
              </div>
            ) : (
              <>
                {lectures.map((lec) => (
                  <button
                    key={lec.lecture_id}
                    onClick={() => navigate(`/workspace/${lec.lecture_id}`)}
                    className="w-full text-left bg-ns border border-bdr2 rounded-xl p-4 flex items-center gap-4 hover:bg-ns2 transition group cursor-pointer shadow-ev2"
                  >
                    <div className="w-10 h-10 rounded-lg bg-ns3 border border-bdr2 flex flex-col items-center justify-center shrink-0">
                      <BookOpen size={16} className="text-nt3 group-hover:text-np transition" />
                    </div>
                    
                    <div className="flex-1 min-w-0">
                      <div className="text-13 font-medium text-nt truncate mb-1">
                        {lec.title || 'Untitled Lecture'}
                      </div>
                      <div className="flex items-center gap-3 text-2xs text-nt4">
                        <span className="flex items-center gap-1">
                          <BookOpen size={10} />
                          {lec.chapter_count || 0} chapters
                        </span>
                        <span className="flex items-center gap-1">
                          <Clock size={10} />
                          {getRelativeTime(lec.created_at)}
                        </span>
                      </div>
                    </div>

                    <ArrowRight 
                      size={16} 
                      className="text-nt4 group-hover:text-nt transition group-hover:translate-x-0.5" 
                    />
                  </button>
                ))}
              </>
            )}
          </div>
        </section>
        
      </div>
    </div>
  )
}