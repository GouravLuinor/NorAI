import { ChapterScreenshots } from '../doc/ChapterScreenshots'
import { PrintSectionCard } from './PrintSectionCard'
import { getCardType } from './cardClassifier'
import { parseChapterContent } from './parseChapter'
import { Markdown } from '../ui/Markdown'
import type { PrintChapterPayload } from './types'

function PrintMarkdown({ children }: { children: string }) {
  return <Markdown variant="print">{children}</Markdown>
}

export function PrintChapter({
  item,
  ch,
  showScreenshots = false,
  continuous = false,
}: {
  item: PrintChapterPayload
  ch: number
  showScreenshots?: boolean
  continuous?: boolean
}) {
  const { title, preamble, sections } = parseChapterContent(item, ch)

  return (
    <div className={continuous ? 'print-flow px-8 py-7' : 'print-chapter px-8 py-7 pb-15'}>
      <h1 className="text-[21px] font-semibold text-nt tracking-tight mb-6">{title}</h1>

      {preamble && <PrintMarkdown>{preamble}</PrintMarkdown>}

      {sections.map((sec, i) => {
        if (!sec.body) return null
        return (
          <PrintSectionCard key={i} type={sec.cardType || getCardType(sec.heading, sec.body)} heading={sec.heading}>
            <PrintMarkdown>{sec.body}</PrintMarkdown>
          </PrintSectionCard>
        )
      })}

      {showScreenshots && <ChapterScreenshots chapterId={ch} startExpanded={true} lazyLoad={false} />}
    </div>
  )
}
