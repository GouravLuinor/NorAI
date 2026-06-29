import { useState } from 'react'
import { ChevronLeft, ChevronRight } from 'lucide-react'

interface Flashcard {
  id: number
  front: string
  back: string
  tip?: string
}

const mockCards: Flashcard[] = [
  {
    id: 1,
    front: 'What is the vanishing gradient problem, and which activation function most commonly causes it?',
    back: 'Gradients shrink exponentially when propagated through layers with sigmoid. Sigmoid\'s derivative ≤0.25 causes this.',
    tip: 'ReLU fixes this – its derivative is 0 or 1.',
  },
  {
    id: 2,
    front: 'What is the time complexity of a Segment Tree range query and point update?',
    back: 'Both are O(log N).',
    tip: 'Tree height is log N; at most 4 nodes visited per level.',
  },
  {
    id: 3,
    front: 'What does a Prefix Sum Array sacrifice for O(1) queries?',
    back: 'Update speed – changing one element requires O(N) recomputation.',
    tip: 'Prefix sums are efficient only for static arrays.',
  },
]

export function FlashcardsPanel() {
  const [current, setCurrent] = useState(0)
  const [flipped, setFlipped] = useState(false)
  const [rating, setRating] = useState('')

  const card = mockCards[current]
  const total = mockCards.length

  const goTo = (idx: number) => {
    setCurrent(Math.max(0, Math.min(total - 1, idx)))
    setFlipped(false)
    setRating('')
  }

  return (
    <div className="flex-1 flex flex-col overflow-hidden">
      {/* Header */}
      <div className="flex items-center justify-between px-5 py-3 border-b border-bdr shrink-0">
        <div>
          <h3 className="text-sm font-semibold text-nt">Ch 01 · Segment Trees</h3>
          <p className="text-[10px] text-nt3">Studying {total} due cards</p>
        </div>
      </div>

      {/* Pips */}
      <div className="flex justify-center gap-1 px-5 py-3">
        {mockCards.map((_, i) => (
          <div key={i} className={`h-1 flex-1 max-w-[20px] rounded-sm ${i < current ? 'bg-nt3' : i === current ? 'bg-np animate-pulse' : 'bg-ns3'}`} />
        ))}
      </div>

      {/* Card – constrained to AI panel width */}
      <div className="flex-1 flex flex-col items-center px-4 pb-4 overflow-y-auto doc-content">
        <div className="w-full max-w-[220px] aspect-[4/3] cursor-pointer perspective-1000 mx-auto"
          onClick={() => setFlipped(!flipped)}>
          <div className={`absolute inset-0 transition-transform duration-500 transform-style-3d ${flipped ? 'rotate-y-180' : ''}`}
            style={{ position: 'relative', width: '100%', height: '100%' }}>
            {/* Front */}
            <div className="absolute inset-0 bg-ns border border-bdr2 rounded-xl p-4 flex flex-col items-center justify-center backface-hidden">
              <span className="text-[10px] font-semibold text-nt3 uppercase tracking-wider mb-3">Front</span>
              <p className="text-sm font-medium text-nt text-center leading-relaxed break-words">{card.front}</p>
            </div>
            {/* Back */}
            <div className="absolute inset-0 bg-ns border border-bdr2 rounded-xl p-4 flex flex-col items-center justify-center backface-hidden rotate-y-180">
              <span className="text-[10px] font-semibold text-np uppercase tracking-wider mb-3">Back</span>
              <p className="text-xs text-nt2 text-center leading-relaxed break-words">{card.back}</p>
              {card.tip && (
                <div className="flex items-start gap-2 mt-3 p-2 bg-nb border border-bdr2 rounded-lg w-full">
                  <div className="w-4 h-4 rounded bg-gradient-to-br from-np to-nbl flex items-center justify-center text-[8px] font-bold text-white shrink-0">N</div>
                  <p className="text-[10px] text-nt2 break-words"><strong className="text-np">Hint:</strong> {card.tip}</p>
                </div>
              )}
            </div>
          </div>
        </div>

        {/* Show Answer / Rating */}
        <div className="mt-4 w-full max-w-[220px] flex justify-center">
          {!flipped ? (
            <button onClick={() => setFlipped(true)}
              className="py-2 px-5 rounded-lg bg-ns2 border border-bdr2 text-nt text-xs font-medium hover:bg-ns3 transition w-full">
              Show Answer
            </button>
          ) : (
            <div className="flex gap-1.5 w-full">
              {['Again', 'Hard', 'Good', 'Easy'].map((r) => (
                <button key={r} onClick={() => setRating(r)}
                  className={`flex-1 py-1.5 rounded-lg text-[10px] font-medium transition ${rating === r ? 'bg-np text-white' : 'bg-ns border border-bdr2 text-nt2 hover:bg-ns2'}`}>
                  {r}
                </button>
              ))}
            </div>
          )}
        </div>

        {/* Navigation */}
        <div className="flex items-center justify-between w-full max-w-[220px] mt-4 pt-3 border-t border-bdr">
          <button onClick={() => goTo(current - 1)} disabled={current === 0}
            className="flex items-center gap-1 px-2 py-1 rounded-md border border-bdr2 text-nt3 text-xs hover:bg-ns2 transition disabled:opacity-40">
            <ChevronLeft size={14} /> Prev
          </button>
          <span className="text-xs text-nt3">{current + 1}/{total}</span>
          <button onClick={() => goTo(current + 1)} disabled={current === total - 1}
            className="flex items-center gap-1 px-2 py-1 rounded-md border border-bdr2 text-nt3 text-xs hover:bg-ns2 transition disabled:opacity-40">
            Next <ChevronRight size={14} />
          </button>
        </div>
      </div>

      {/* Stats footer */}
      <div className="flex justify-around items-center px-4 py-2 border-t border-bdr bg-ns2 shrink-0">
        <div className="text-center">
          <div className="text-base font-mono font-semibold text-nt">{current + 1}</div>
          <div className="text-[9px] text-nt3 uppercase tracking-wider">Reviewed</div>
        </div>
        <div className="text-center">
          <div className="text-base font-mono font-semibold text-ng">2</div>
          <div className="text-[9px] text-nt3 uppercase tracking-wider">Got it</div>
        </div>
        <div className="text-center">
          <div className="text-base font-mono font-semibold text-na">1</div>
          <div className="text-[9px] text-nt3 uppercase tracking-wider">Almost</div>
        </div>
        <div className="text-center">
          <div className="text-base font-mono font-semibold text-nt3">{total - current - 1}</div>
          <div className="text-[9px] text-nt3 uppercase tracking-wider">Left</div>
        </div>
      </div>
    </div>
  )
}