import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Sparkles, Film, Upload, Link2, FileVideo } from 'lucide-react'

type InputType = 'youtube' | 'upload' | 'drive'

export function UploadPage() {
  const [inputType, setInputType] = useState<InputType>('youtube')
  const [url, setUrl] = useState('')
  const [file, setFile] = useState<File | null>(null)
  const navigate = useNavigate()

  const handleStart = async () => {
    // Build form data and POST to /process
    const formData = new FormData()
    formData.append('source_type', inputType)
    if (inputType === 'upload' && file) {
      formData.append('file', file)
    } else {
      formData.append('url', url)
    }

    const res = await fetch('/process', { method: 'POST', body: formData })
    const { task_id } = await res.json()
    // Navigate to processing page with task_id
    navigate(`/process/${task_id}`)
  }

  const canSubmit =
    (inputType === 'upload' && file) ||
    ((inputType === 'youtube' || inputType === 'drive') && url.trim())

  return (
    <div className="h-screen bg-nb flex items-center justify-center p-8">
      <div className="w-full max-w-lg">
        {/* Logo & Tagline */}
        <div className="text-center mb-10">
          <div className="flex items-center justify-center gap-2 mb-4">
            <div className="w-10 h-10 rounded-lg bg-np flex items-center justify-center text-lg font-semibold text-white shadow-lg">
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
        <div className="bg-ns border border-bdr2 rounded-xl p-6 shadow-2xl">
          {/* Segmented Control */}
          <div className="flex bg-nb rounded-lg p-1 mb-5">
            {([
              ['youtube', Film, 'YouTube'],
              ['upload', Upload, 'Upload'],
              ['drive', Link2, 'Drive'],
            ] as const).map(([type, Icon, label]) => (
              <button
                key={type}
                onClick={() => setInputType(type)}
                className={`flex-1 flex items-center justify-center gap-2 py-2 rounded-md text-[12px] font-medium transition ${
                  inputType === type
                    ? 'bg-ns3 text-nt shadow-sm'
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
            <label className="flex flex-col items-center justify-center gap-3 p-10 border-2 border-dashed border-bdr2 rounded-lg cursor-pointer hover:border-np transition">
              <FileVideo size={32} className="text-nt3" />
              <span className="text-[13px] text-nt2">
                {file ? file.name : 'Click or drag a video file here'}
              </span>
              <span className="text-[10px] text-nt4">MP4, MKV, WebM up to 2 GB</span>
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
                className="w-full bg-nb border border-bdr2 rounded-lg px-4 py-3 pr-12 text-[13px] text-nt placeholder:text-nt4 outline-none focus:border-np transition"
              />
              <div className="absolute right-3 top-1/2 -translate-y-1/2 text-nt3">
                {inputType === 'youtube' ? <Film size={16} /> : <Link2 size={16} />}
              </div>
            </div>
          )}

          {/* Submit Button */}
          <button
            onClick={handleStart}
            disabled={!canSubmit}
            className="w-full mt-5 flex items-center justify-center gap-2 py-3 rounded-lg bg-np text-white text-[13px] font-medium shadow-lg hover:bg-[#8E82E0] transition disabled:opacity-40 disabled:cursor-not-allowed"
          >
            <Sparkles size={15} />
            Start Processing
          </button>
        </div>

        {/* Footer Hint */}
        <p className="text-center text-[11px] text-nt4 mt-6">
          ⓘ Works with lectures up to 3 hours.
          We'll generate notes, revision sheets, quizzes & more.
        </p>
      </div>
    </div>
  )
}