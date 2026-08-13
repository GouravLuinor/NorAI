import { useState, useEffect, useLayoutEffect, useCallback, useMemo } from 'react'
import { ChevronLeft, ChevronRight, Download } from 'lucide-react'
import {
  fetchGeneratedFlashcards,
  fetchFlashcardRatings,
  persistFlashcardRatings,
  downloadFlashcardsApkg,
  type Flashcard,
  type FlashcardScheduleMap,
} from '../../stores/useQuizStore'
import { useChapterStore } from '../../stores/useChapterStore'
import { useLectureStore } from '../../stores/useLectureStore'
import { getCardKey } from '../../lib/hash'
import { isCardDue, dueLabel } from '../../lib/flashcardSchedule'
import { Button } from '../ui/Button'
import { SegmentedControl } from '../ui/SegmentedControl'
import { useToastStore } from '../../stores/useToastStore'
import { FOCUS_RING } from '../ui/shared'

type Rating = 'Again' | 'Hard' | 'Good' | 'Easy'
type FilterMode = 'all' | 'missed' | 'due'

export function FlashcardsPanel() {
  const { activeChapterId } = useChapterStore()
  const lectureId = useLectureStore(s => s.activeLectureId) || 'default'
  const addToast = useToastStore(s => s.addToast)

  const [allCards, setAllCards] = useState<Flashcard[]>([])
  const [cardKeys, setCardKeys] = useState<string[]>([])
  const [current, setCurrent] = useState(0)
  const [flipped, setFlipped] = useState(false)
  const [rating, setRating] = useState<Rating | ''>('')
  const [ratings, setRatings] = useState<Record<string, Rating>>({})
  const [schedule, setSchedule] = useState<FlashcardScheduleMap>({})
  const [filter, setFilter] = useState<FilterMode>('all')
  const [exporting, setExporting] = useState(false)

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

  // Load persisted ratings + SM-2 schedule
  useEffect(() => {
    fetchFlashcardRatings(lectureId, activeChapterId)
      .then((data) => {
        setRatings(data.ratings as Record<string, Rating>)
        setSchedule(data.schedule)
      })
      .catch(() => {
        setRatings({})
        setSchedule({})
      })
  }, [lectureId, activeChapterId])

  // Apply the active deck filter
  const cards = useMemo(() => {
    if (filter === 'all') return allCards
    return allCards.filter((_, idx) => {
      const key = cardKeys[idx]
      if (filter === 'missed') {
        const r = ratings[key]
        return r === 'Again' || r === 'Hard'
      }
      return isCardDue(schedule[key])
    })
  }, [allCards, cardKeys, ratings, schedule, filter])

  const total = cards.length
  const reviewed = cardKeys.filter((key) => ratings[key]).length
  const gotIt = cardKeys.filter((key) => ratings[key] === 'Good' || ratings[key] === 'Easy').length
  const almost = cardKeys.filter((key) => ratings[key] === 'Again' || ratings[key] === 'Hard').length
  const left = Math.max(0, allCards.length - reviewed)
  const dueCount = cardKeys.filter((key) => isCardDue(schedule[key])).length

  useLayoutEffect(() => {
    if (cards.length > 0 && current >= cards.length) {
      setCurrent(cards.length - 1)
    }
  }, [current, cards.length])

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
    const next = await persistFlashcardRatings([{ card_key: key, rating: r }], lectureId, activeChapterId)
    if (next) setSchedule((prev) => ({ ...prev, ...next }))

    setTimeout(() => {
      if (current < total - 1) {
        goTo(current + 1)
      }
    }, 400)
  }

  const handleExport = async () => {
    if (exporting) return
    setExporting(true)
    const ok = await downloadFlashcardsApkg(lectureId)
    addToast(ok ? 'Anki deck downloaded' : 'Anki export failed', ok ? 'success' : 'error')
    setExporting(false)
  }

  if (allCards.length === 0) {
    return (
      <div className="flex-1 flex items-center justify-center text-nt3 text-sm">
        No flashcards available.
      </div>
    )
  }

  if (total === 0) {
    return (
      <div className="flex-1 flex flex-col items-center justify-center p-6 text-center gap-3">
        <p className="text-sm font-medium text-nt">
          {filter === 'missed' ? 'No missed cards found!' : 'No cards due right now!'}
        </p>
        <p className="text-2xs text-nt3">
          {filter === 'missed'
            ? 'You haven’t marked any cards as "Again" or "Hard" yet.'
            : 'Come back when a card’s next review arrives — or study the full deck.'}
        </p>
        <Button
          variant="outline"
          onClick={() => { setFilter('all'); setCurrent(0) }}
          className="text-xs py-1.5 px-3 border-bdr2"
        >
          Show All Cards
        </Button>
      </div>
    )
  }

  const card = cards[current]
  const cardKey = card ? cardKeys[allCards.indexOf(card)] : undefined

  return (
    <div className="flex-1 flex flex-col overflow-hidden">
      {/* Header */}
      <div className="flex items-center justify-between px-5 py-3 border-b border-bdr shrink-0">
        <div>
          <h2 className="text-sm font-semibold text-nt">Flashcards</h2>
          <p className="text-2xs text-nt3">
            Studying {total} {filter !== 'all' ? `${filter} ` : ''}cards
            {dueCount > 0 ? ` · ${dueCount} due` : ''}
          </p>
        </div>

        <Button
          variant="outline"
          onClick={handleExport}
          disabled={exporting}
          className="flex items-center gap-1.5 text-xs px-2.5 py-1.5 rounded border-bdr2 bg-transparent"
        >
          <Download size={13} />
          <span>{exporting ? 'Exporting…' : 'Export Anki'}</span>
        </Button>
      </div>

      {/* Deck filter toolbar */}
      <div className="flex items-center justify-between px-5 py-2 border-b border-bdr shrink-0 gap-2">
        <div className="flex items-center gap-1 p-0.5 bg-ns2 border border-bdr rounded-sm">
          {(['all', 'missed', 'due'] as FilterMode[]).map((m) => (
            <button
              key={m}
              type="button"
              aria-pressed={filter === m}
              onClick={() => { setFilter(m); setCurrent(0) }}
              className={`px-2.5 py-1 rounded-[3px] text-[11px] font-medium transition ${
                filter === m ? 'bg-npf text-npfg shadow-ev2' : 'text-nt2 hover:bg-ns3'
              }`}
            >
              {m === 'all' ? 'All' : m === 'missed' ? 'Missed' : 'Due'}
            </button>
          ))}
        </div>
        <span className="text-2xs text-nt3 tabular-nums">{reviewed}/{allCards.length} reviewed</span>
      </div>

      {/* Pips */}
      <div aria-hidden="true" className="flex justify-center gap-1 px-5 py-3 pb-1">
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
              <span
                className={`mb-3 text-[10px] font-semibold uppercase tracking-wider px-2 py-0.5 rounded-full border ${
                  isCardDue(cardKey ? schedule[cardKey] : undefined)
                    ? 'bg-na/10 text-na border-na/25'
                    : 'bg-ns2 text-nt3 border-bdr2'
                }`}
              >
                {dueLabel(cardKey ? schedule[cardKey] : undefined)}
              </span>
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