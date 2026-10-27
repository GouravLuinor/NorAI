import { Plus } from 'lucide-react'
import type { FaqItem } from '../../content/faq'

/**
 * Native <details> so answers are in the HTML (crawlable, quotable) and work
 * without JS. The first sentence of each answer is the direct answer.
 */
export function FaqList({ items }: { items: FaqItem[] }) {
  return (
    <div className="divide-y divide-bdr border-y border-bdr">
      {items.map((item) => (
        <details key={item.q} className="group py-4">
          <summary className="flex cursor-pointer list-none items-start justify-between gap-4 text-left rounded-sm focus-visible:outline-2 focus-visible:outline-np [&::-webkit-details-marker]:hidden">
            <h3 className="font-serif text-17 text-nt">{item.q}</h3>
            <Plus
              size={16}
              aria-hidden="true"
              className="mt-1 shrink-0 text-nt3 transition-transform duration-200 group-open:rotate-45"
            />
          </summary>
          <p className="mt-2 max-w-prose text-14 leading-relaxed text-nt2">{item.a}</p>
        </details>
      ))}
    </div>
  )
}
