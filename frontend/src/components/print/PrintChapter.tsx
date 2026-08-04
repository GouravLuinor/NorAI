import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import remarkMath from 'remark-math'
import rehypeHighlight from 'rehype-highlight'
import rehypeKatex from 'rehype-katex'
import { ChapterScreenshots } from '../doc/ChapterScreenshots'
import { printMarkdownComponents } from '../../lib/markdown'
import { PrintSectionCard } from './PrintSectionCard'
import { getCardType } from './cardClassifier'
import { parseChapterContent } from './parseChapter'

function PrintMarkdown({ children }: { children: string }) {
  return (
    <ReactMarkdown
      remarkPlugins={[remarkGfm, remarkMath]}
      rehypePlugins={[rehypeHighlight, rehypeKatex]}
      components={printMarkdownComponents}
    >
      {children}
    </ReactMarkdown>
  )
}

export function PrintChapter({
  item,
  ch,
  showScreenshots = false,
}: {
  item: any
  ch: number
  showScreenshots?: boolean
}) {
  const { title, preamble, sections } = parseChapterContent(item, ch)

  return (
    <div className="print-chapter px-8 py-7 pb-15">
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
