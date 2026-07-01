import { useState, useEffect, useCallback } from 'react'
import { ChevronLeft, ChevronRight } from 'lucide-react'
import { fetchGeneratedFlashcards } from '../../stores/useQuizStore'
import { useChapterStore } from '../../stores/useChapterStore'

interface Flashcard {
  front: string
  back: string
  explanation?: string
}

type Rating = 'Again' | 'Hard' | 'Good' | 'Easy'

export function FlashcardsPanel() {
  const { activeChapterId } = useChapterStore()
  const [cards, setCards] = useState<Flashcard[]>([])
  const [current, setCurrent] = useState(0)
  const [flipped, setFlipped] = useState(false)
  const [rating, setRating] = useState<Rating | ''>('')
  const [ratings, setRatings] = useState<Record<number, Rating>>({})   // card index → rating

  useEffect(() => {
    fetchGeneratedFlashcards(activeChapterId).then(setCards).catch(() => setCards([]))
  }, [activeChapterId])

  const total = cards.length
  const reviewed = Object.keys(ratings).length
  const gotIt = Object.values(ratings).filter((r) => r === 'Good' || r === 'Easy').length
  const almost = Object.values(ratings).filter((r) => r === 'Again' || r === 'Hard').length
  const left = total - reviewed

  const goTo = useCallback((idx: number) => {
    setCurrent(Math.max(0, Math.min(total - 1, idx)))
    setFlipped(false)
    setRating('')
  }, [total])

  const handleRate = (r: Rating) => {
    setRatings((prev) => ({ ...prev, [current]: r }))
    setRating(r)
    // auto‑advance after a short delay so the user sees the selected rating
    setTimeout(() => {
      if (current < total - 1) {
        goTo(current + 1)
      }
    }, 400)
  }

  if (total === 0) {
    return (
      <div className="flex-1 flex items-center justify-center text-nt3 text-sm">
        No flashcards available.
      </div>
    )
  }

  const card = cards[current]

  return (
    <div className="flex-1 flex flex-col overflow-hidden">
      {/* Header */}
      <div className="flex items-center justify-between px-5 py-3 border-b border-bdr shrink-0">
        <div>
          <h3 className="text-sm font-semibold text-nt">Flashcards</h3>
          <p className="text-[10px] text-nt3">Studying {total} cards</p>
        </div>
      </div>

      {/* Pips */}
      <div className="flex justify-center gap-1 px-5 py-3">
        {cards.map((_, i) => (
          <div
            key={i}
            className={`h-1 flex-1 max-w-[20px] rounded-sm ${
              i < current ? 'bg-nt3' : i === current ? 'bg-np animate-pulse' : 'bg-ns3'
            }`}
          />
        ))}
      </div>

      {/* Card – responsive */}
      <div className="flex-1 flex flex-col items-center px-4 pb-4 overflow-y-auto doc-content">
        <div
          className="w-full max-w-[90%] aspect-[4/3] cursor-pointer perspective-1000 mx-auto"
          onClick={() => setFlipped(!flipped)}
        >
          <div
            className={`relative w-full h-full transition-transform duration-500 transform-style-3d ${
              flipped ? 'rotate-y-180' : ''
            }`}
          >
            {/* Front */}
            <div className="absolute inset-0 bg-ns border border-bdr2 rounded-xl p-5 flex flex-col items-center justify-center backface-hidden">
              <span className="text-[10px] font-semibold text-nt3 uppercase tracking-wider mb-4">Front</span>
              <p className="text-sm font-medium text-nt text-center leading-relaxed break-words px-2">
                {card.front}
              </p>
            </div>
            {/* Back */}
            <div className="absolute inset-0 bg-ns border border-bdr2 rounded-xl p-5 flex flex-col items-center justify-center backface-hidden rotate-y-180">
              <span className="text-[10px] font-semibold text-np uppercase tracking-wider mb-4">Back</span>
              <p className="text-sm text-nt2 text-center leading-relaxed break-words px-2">
                {card.back}
              </p>
              {card.explanation && (
                <div className="flex items-start gap-2 mt-4 p-3 bg-nb border border-bdr2 rounded-lg w-full max-w-[85%]">
                  <div className="w-5 h-5 rounded-md bg-gradient-to-br from-np to-nbl flex items-center justify-center text-[9px] font-bold text-white shrink-0">
                    N
                  </div>
                  <p className="text-[11px] text-nt2 break-words leading-relaxed">
                    <strong className="text-np">Hint:</strong> {card.explanation}
                  </p>
                </div>
              )}
            </div>
          </div>
        </div>

        {/* Show Answer / Rating */}
        <div className="mt-5 w-full max-w-[90%] flex justify-center">
          {!flipped ? (
            <button
              onClick={() => setFlipped(true)}
              className="py-2.5 px-6 rounded-lg bg-ns2 border border-bdr2 text-nt text-sm font-medium hover:bg-ns3 transition w-full"
            >
              Show Answer
            </button>
          ) : (
            <div className="flex gap-2 w-full">
              {(['Again', 'Hard', 'Good', 'Easy'] as Rating[]).map((r) => (
                <button
                  key={r}
                  onClick={() => handleRate(r)}
                  className={`flex-1 py-2 rounded-lg text-[11px] font-medium transition ${
                    rating === r
                      ? 'bg-np text-white'
                      : 'bg-ns border border-bdr2 text-nt2 hover:bg-ns2'
                  }`}
                >
                  {r}
                </button>
              ))}
            </div>
          )}
        </div>

        {/* Navigation */}
        <div className="flex items-center justify-between w-full max-w-[90%] mt-5 pt-4 border-t border-bdr">
          <button
            onClick={() => goTo(current - 1)}
            disabled={current === 0}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-md border border-bdr2 text-nt3 text-xs hover:bg-ns2 transition disabled:opacity-40"
          >
            <ChevronLeft size={15} /> Prev
          </button>
          <span className="text-xs text-nt3">
            {current + 1} / {total}
          </span>
          <button
            onClick={() => goTo(current + 1)}
            disabled={current === total - 1}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-md border border-bdr2 text-nt3 text-xs hover:bg-ns2 transition disabled:opacity-40"
          >
            Next <ChevronRight size={15} />
          </button>
        </div>
      </div>

      {/* Stats footer — now dynamic */}
      <div className="flex justify-around items-center px-4 py-2 border-t border-bdr bg-ns2 shrink-0">
        <div className="text-center">
          <div className="text-base font-mono font-semibold text-nt">{reviewed}</div>
          <div className="text-[9px] text-nt3 uppercase tracking-wider">Reviewed</div>
        </div>
        <div className="text-center">
          <div className="text-base font-mono font-semibold text-ng">{gotIt}</div>
          <div className="text-[9px] text-nt3 uppercase tracking-wider">Got it</div>
        </div>
        <div className="text-center">
          <div className="text-base font-mono font-semibold text-na">{almost}</div>
          <div className="text-[9px] text-nt3 uppercase tracking-wider">Almost</div>
        </div>
        <div className="text-center">
          <div className="text-base font-mono font-semibold text-nt3">{left}</div>
          <div className="text-[9px] text-nt3 uppercase tracking-wider">Left</div>
        </div>
      </div>
    </div>
  )
}