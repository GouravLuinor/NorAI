import { Bookmark, Image } from 'lucide-react'

interface EvidenceCardProps {
  type: 'note' | 'media'
  kicker: string
  title: string
  thumbnail?: boolean
  onClick?: () => void
}

export function EvidenceCard({ type, kicker, title, thumbnail, onClick }: EvidenceCardProps) {
  return (
    <div
      onClick={onClick}
      className="flex flex-col bg-ns2 border border-bdr2 rounded-lg my-3 overflow-hidden cursor-pointer transition-colors hover:border-bdr"
    >
      <div className="flex items-center gap-3 px-3.5 py-3">
        <div className="w-7 h-7 rounded-md bg-ns flex items-center justify-center shrink-0 shadow-sm">
          {type === 'note' ? (
            <Bookmark size={14} className="text-np" />
          ) : (
            <Image size={14} className="text-nbl" />
          )}
        </div>
        <div className="flex flex-col flex-1 min-w-0">
          <span className="text-[9.5px] font-semibold text-nt3 uppercase tracking-wider">
            {kicker}
          </span>
          <span className="text-[13px] font-semibold text-nt truncate">{title}</span>
        </div>
      </div>
      {thumbnail && (
        <div className="h-[60px] bg-ns3 border-t border-bdr flex items-center justify-center text-nt4">
          <Image size={28} />
        </div>
      )}
    </div>
  )
}