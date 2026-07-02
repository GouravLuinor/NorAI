import { useEffect, useCallback } from 'react'
import { X } from 'lucide-react'

interface LightboxProps {
  src: string
  alt?: string
  caption?: string
  onClose: () => void
}

export function Lightbox({ src, alt = '', caption = '', onClose }: LightboxProps) {
  const handleKeyDown = useCallback(
    (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose()
    },
    [onClose]
  )

  useEffect(() => {
    document.addEventListener('keydown', handleKeyDown)
    document.body.style.overflow = 'hidden' // prevent background scroll
    return () => {
      document.removeEventListener('keydown', handleKeyDown)
      document.body.style.overflow = ''
    }
  }, [handleKeyDown])

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-sm p-8"
      onClick={onClose}
    >
      {/* Close button */}
      <button
        onClick={onClose}
        className="absolute top-4 right-4 w-8 h-8 rounded-md bg-ns2 border border-bdr2 text-nt3 hover:text-nt hover:bg-ns3 transition flex items-center justify-center"
        aria-label="Close lightbox"
      >
        <X size={16} />
      </button>

      {/* Image container */}
      <div
        className="max-w-full max-h-full flex flex-col items-center"
        onClick={(e) => e.stopPropagation()} // prevent closing when clicking image
      >
        <img
          src={src}
          alt={alt}
          className="max-w-full max-h-[80vh] object-contain rounded-lg shadow-2xl"
        />
        {caption && (
          <p className="mt-4 text-sm text-nt2 text-center max-w-lg leading-relaxed">
            {caption}
          </p>
        )}
      </div>
    </div>
  )
}