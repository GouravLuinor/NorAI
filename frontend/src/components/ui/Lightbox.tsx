import { useEffect, useCallback } from 'react'
import { X } from 'lucide-react'
import { IconButton } from './IconButton'

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
      <IconButton
        label="Close lightbox"
        onClick={onClose}
        className="absolute top-4 right-4 w-8 h-8 rounded-md bg-ns2 border border-bdr2"
      >
        <X size={16} strokeWidth={1.5} />
      </IconButton>

      {/* Image container */}
      <div
        className="max-w-full max-h-full flex flex-col items-center"
        onClick={(e) => e.stopPropagation()} // prevent closing when clicking image
      >
        <img
          src={src}
          alt={alt}
          className="max-w-full max-h-[80vh] object-contain rounded-lg shadow-ev3"
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