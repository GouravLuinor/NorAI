import { X } from 'lucide-react'
import { IconButton } from './IconButton'
import { Dialog } from './Dialog'

interface LightboxProps {
  src: string
  alt?: string
  caption?: string
  onClose: () => void
}

export function Lightbox({ src, alt = '', caption = '', onClose }: LightboxProps) {
  return (
    <Dialog
      ariaLabel={alt || 'Image preview'}
      ariaDescribedBy={caption ? 'lightbox-caption' : undefined}
      onClose={onClose}
      overlayClassName="bg-black/70 backdrop-blur-sm p-8"
      panelClassName="max-w-full max-h-full flex flex-col items-center"
    >
      {/* Close button */}
      <IconButton
        label="Close lightbox"
        onClick={onClose}
        className="absolute top-4 right-4 w-8 h-8 rounded-md bg-ns2 border border-bdr2"
      >
        <X size={16} strokeWidth={1.5} />
      </IconButton>

      <img
        src={src}
        alt={alt}
        width="1600"
        height="900"
        className="max-w-full max-h-[80vh] object-contain rounded-lg shadow-ev3 w-auto h-auto"
      />
      {caption && (
        <p id="lightbox-caption" className="mt-4 text-sm text-nt2 text-center max-w-lg leading-relaxed">
          {caption}
        </p>
      )}
    </Dialog>
  )
}
