import { useState, useEffect, useCallback, useMemo } from 'react'
import { ChevronLeft, ChevronRight, Filter } from 'lucide-react'
import { fetchGeneratedFlashcards, fetchFlashcardRatings, persistFlashcardRatings, type Flashcard } from '../../stores/useQuizStore'
import { useChapterStore } from '../../stores/useChapterStore'
import { useLectureStore } from '../../stores/useLectureStore'
import { getCardKey } from '../../lib/hash'
import { Button } from '../ui/Button'
import { SegmentedControl } from '../ui/SegmentedControl'
import { FOCUS_RING } from '../ui/shared'

type Rating = 'Again' | 'Hard' | 'Good' | 'Easy'

export function FlashcardsPanel() {
  const { activeChapterId } = useChapterStore()
  const lectureId = useLectureStore(s => s.activeLectureId) || 'default'

  const [allCards, setAllCards] = useState<Flashcard[]>([])
  const [cardKeys, setCardKeys] = useState<string[]>([])
  const [current, setCurrent] = useState(0)
  const [flipped, setFlipped] = useState(false)
  const [rating, setRating] = useState<Rating | ''>('')
  const [ratings, setRatings] = useState<Record<string, Rating>>({})
  const [filterMissedOnly, setFilterMissedOnly] = useState(false)

  // Load cards and compute keys
  useEffect(() => {
    fetchGeneratedFlashcards(activeChapterId, lectureId)
      .then(async (fetched) => {
        setAllCards(fetched)
        const keys = await Promise.all(fetched.map((c) => getCardKey(c.front)))
        setCardKeys(keys)
      })
      .catch(() => {
        setAllCards([])
        setCardKeys([])
      })
  }, [activeChapterId, lectureId])

  // Load persisted ratings
  useEffect(() => {
    fetchFlashcardRatings(lectureId, activeChapterId)
      .then((persisted) => setRatings(persisted as Record<string, Rating>))
      .catch(() => setRatings({}))
  }, [lectureId, activeChapterId])

  // Subsample missed (Again / Hard) cards if filter active
  const cards = useMemo(() => {
    if (!filterMissedOnly) return allCards
    return allCards.filter((_, idx) => {
      const key = cardKeys[idx]
      const r = ratings[key]
      return r === 'Again' || r === 'Hard'
    })
  }, [allCards, cardKeys, ratings, filterMissedOnly])

  const total = cards.length
  const reviewed = cardKeys.filter((key) => ratings[key]).length
  const gotIt = cardKeys.filter((key) => ratings[key] === 'Good' || ratings[key] === 'Easy').length
  const almost = cardKeys.filter((key) => ratings[key] === 'Again' || ratings[key] === 'Hard').length
  const left = Math.max(0, allCards.length - reviewed)

  const goTo = useCallback((idx: number) => {
    setCurrent(Math.max(0, Math.min(total - 1, idx)))
    setFlipped(false)
    setRating('')
  }, [total])

  const handleRate = async (r: Rating) => {
    const card = cards[current]
    if (!card) return
    const key = await getCardKey(card.front)
    setRatings((prev) => ({ ...prev, [key]: r }))
    setRating(r)
    persistFlashcardRatings([{ card_key: key, rating: r }], lectureId, activeChapterId)

    setTimeout(() => {
      if (current < total - 1) {
        goTo(current + 1)
      }
    }, 400)
  }

  if (allCards.length === 0) {
    return (
      <div className="flex-1 flex items-center justify-center text-nt3 text-sm">
        No flashcards available.
      </div>
    )
  }

  if (filterMissedOnly && total === 0) {
    return (
      <div className="flex-1 flex flex-col items-center justify-center p-6 text-center gap-3">
        <p className="text-sm font-medium text-nt">No missed cards found!</p>
        <p className="text-2xs text-nt3">You haven't marked any cards as "Again" or "Hard" yet.</p>
        <Button
          variant="outline"
          onClick={() => setFilterMissedOnly(false)}
          className="text-xs py-1.5 px-3 border-bdr2"
        >
          Show All Cards
        </Button>
      </div>
    )
  }

  const card = cards[current]

  return (
    <div className="flex-1 flex flex-col overflow-hidden">
      {/* Header */}
      <div className="flex items-center justify-between px-5 py-3 border-b border-bdr shrink-0">
        <div>
          <h2 className="text-sm font-semibold text-nt">Flashcards</h2>
          <p className="text-2xs text-nt3">
            Studying {total} {filterMissedOnly ? 'missed' : ''} cards
          </p>
        </div>

        <button
          type="button"
          onClick={() => {
            setFilterMissedOnly(!filterMissedOnly)
            setCurrent(0)
          }}
          className={`flex items-center gap-1.5 text-xs px-2.5 py-1 rounded border transition ${
            filterMissedOnly
              ? 'bg-npf text-npfg border-np'
              : 'bg-ns2 text-nt2 border-bdr2 hover:bg-ns3'
          }`}
        >
          <Filter size={13} />
          <span>{filterMissedOnly ? 'Missed Only' : 'All Cards'}</span>
        </button>
      </div>

      {/* Pips */}
      <div aria-hidden="true" className="flex justify-center gap-1 px-5 py-3">
        {cards.map((_, i) => (
          <div
            key={i}
            className={`h-1 flex-1 max-w-[20px] rounded-sm ${
              i < current ? 'bg-nt3' : i === current ? 'bg-np animate-pulse' : 'bg-ns3'
            }`}
          />
        ))}
      </div>
      <span className="sr-only">Card {current + 1} of {total}</span>

      {/* Card – responsive */}
      <div className="flex-1 flex flex-col items-center px-4 pb-4 overflow-y-auto doc-content">
        <button
          type="button"
          aria-pressed={flipped}
          className={`w-full max-w-[90%] aspect-[4/3] cursor-pointer perspective-1000 mx-auto block p-0 ${FOCUS_RING}`}
          onClick={() => setFlipped(!flipped)}
        >
          <div
            className={`relative w-full h-full transition-transform duration-500 transform-style-3d ${
              flipped ? 'rotate-y-180' : ''
            }`}
          >
            {/* Front */}
            <div aria-hidden={flipped || undefined} className="absolute inset-0 bg-ns border border-bdr2 rounded-xl p-5 flex flex-col items-center justify-center backface-hidden">
              <span className="text-2xs font-semibold text-nt3 uppercase tracking-wider mb-4">Front</span>
              <p className="text-sm font-medium text-nt text-center leading-relaxed break-words px-2">
                {card?.front}
              </p>
            </div>
            {/* Back */}
            <div aria-hidden={flipped ? undefined : true} className="absolute inset-0 bg-ns border border-bdr2 rounded-xl p-5 flex flex-col items-center justify-center backface-hidden rotate-y-180">
              <span className="spec-label mb-4">Back</span>
              <p className="text-sm text-nt2 text-center leading-relaxed break-words px-2">
                {card?.back}
              </p>
              {card?.explanation && (
                <div className="flex items-start gap-2 mt-4 p-3 bg-nb border border-bdr2 rounded-md w-full max-w-[85%]">
                  <div className="w-5 h-5 rounded-sm bg-npf flex items-center justify-center text-3xs font-bold text-npfg shrink-0">
                    N
                  </div>
                  <p className="text-11 text-nt2 break-words leading-relaxed">
                    <strong className="text-np">Hint:</strong> {card.explanation}
                  </p>
                </div>
              )}
            </div>
          </div>
        </button>

        {/* Show Answer / Rating */}
        <div className="mt-5 w-full max-w-[90%] flex justify-center">
          {!flipped ? (
            <Button
              variant="surface"
              onClick={() => setFlipped(true)}
              className="py-2.5 px-6 rounded-md w-full text-sm bg-ns2 hover:bg-ns3 active:translate-y-[1px] active:shadow-none"
            >
              Show Answer
            </Button>
          ) : (
            <div className="flex gap-2 w-full">
              <SegmentedControl<Rating>
                containerClass="flex gap-2 w-full"
                itemClass="flex-1 py-2 rounded-sm text-11 font-medium transition active:translate-y-[1px]"
                activeClass="bg-npf text-npfg shadow-ev2 active:shadow-none"
                inactiveClass="bg-ns border border-bdr2 text-nt2 hover:bg-ns2"
                options={(['Again', 'Hard', 'Good', 'Easy'] as Rating[]).map((r) => ({ value: r, label: r }))}
                value={rating || null}
                onChange={handleRate}
              />
            </div>
          )}
        </div>

        {/* Navigation */}
        <div className="flex items-center justify-between w-full max-w-[90%] mt-5 pt-4 border-t border-bdr">
          <Button
            variant="outline"
            onClick={() => goTo(current - 1)}
            disabled={current === 0}
            className="gap-1.5 px-3 py-1.5 rounded-md text-xs bg-transparent border-bdr2 disabled:opacity-40"
          >
            <ChevronLeft size={15} strokeWidth={1.5} /> Prev
          </Button>
          <span className="text-xs text-nt3">
            {current + 1} / {total}
          </span>
          <Button
            variant="outline"
            onClick={() => goTo(current + 1)}
            disabled={current === total - 1}
            className="gap-1.5 px-3 py-1.5 rounded-md text-xs bg-transparent border-bdr2 disabled:opacity-40"
          >
            Next <ChevronRight size={15} strokeWidth={1.5} />
          </Button>
        </div>
      </div>

      {/* Stats footer — dynamic */}
      <div className="flex justify-around items-center px-4 py-2 border-t border-bdr bg-ns2 shrink-0">
        <div className="text-center">
          <div className="text-base font-mono font-semibold text-nt">{reviewed}</div>
          <div className="text-3xs text-nt3 uppercase tracking-wider">Reviewed</div>
        </div>
        <div className="text-center">
          <div className="text-base font-mono font-semibold text-ng">{gotIt}</div>
          <div className="text-3xs text-nt3 uppercase tracking-wider">Got it</div>
        </div>
        <div className="text-center">
          <div className="text-base font-mono font-semibold text-na">{almost}</div>
          <div className="text-3xs text-nt3 uppercase tracking-wider">Almost</div>
        </div>
        <div className="text-center">
          <div className="text-base font-mono font-semibold text-nt3">{left}</div>
          <div className="text-3xs text-nt3 uppercase tracking-wider">Left</div>
        </div>
      </div>
    </div>
  )
}