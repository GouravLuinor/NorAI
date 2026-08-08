import { layoutConceptMap, conceptEdgePath, type ConceptMapResponse, type ConceptNode } from '../../lib/conceptMapLayout'

// Static vector rendering of a chapter's concept map for the print route.
// Uses the same shared layout engine as the interactive ConceptMapView so the
// exported PDF matches the on-screen tree. No interactivity by design — this is
// the printable snapshot.
interface PrintConceptMapProps {
  data: ConceptMapResponse
  ch: number
}

interface NodeStyle {
  rx: number
  padX: number
  padY: number
  font: number
  weight: number
  fill: string
  stroke: string
  text: string
}

const NODE_STYLE: Record<ConceptNode['type'], NodeStyle> = {
  root: {
    rx: 22, padX: 20, padY: 10, font: 12, weight: 700,
    fill: 'var(--color-np)', stroke: 'var(--color-np)', text: 'var(--color-ns)',
  },
  focus_concept: {
    rx: 8, padX: 14, padY: 8, font: 10.5, weight: 600,
    fill: 'var(--color-ns2)', stroke: 'var(--color-np)', text: 'var(--color-nt)',
  },
  detail: {
    rx: 6, padX: 10, padY: 6, font: 9, weight: 500,
    fill: 'var(--color-ns)', stroke: 'var(--color-bdr)', text: 'var(--color-nt2)',
  },
}

// Cap box widths so long chapter titles / concept labels never push a node box
// into its neighbor's column. Labels that don't fit are ellipsized (the full
// text is kept as an SVG tooltip + on the page heading).
const MAX_W: Record<ConceptNode['type'], number> = {
  root: 240,
  focus_concept: 200,
  detail: 200,
}

const CHAR_W = 6.5

function fitLabel(node: ConceptNode): { text: string; w: number; h: number } {
  const s = NODE_STYLE[node.type]
  const maxW = MAX_W[node.type]
  const pad = s.padX * 2
  let text = node.label
  if (text.length * CHAR_W + pad > maxW) {
    const capChars = Math.floor((maxW - pad) / CHAR_W)
    text = text.slice(0, Math.max(capChars, 8) - 1).trimEnd() + '…'
  }
  const w = Math.max(text.length * CHAR_W + pad, 64)
  const h = s.font + s.padY * 2 + 4
  return { text, w, h }
}

export function PrintConceptMap({ data, ch }: PrintConceptMapProps) {
  const nodes = Array.isArray(data.nodes) ? data.nodes : []
  const edges = Array.isArray(data.edges) ? data.edges : []
  if (nodes.length === 0) return null

  const positions = layoutConceptMap(nodes, edges, 'tree', { height: 600 })
  const fitted = Object.fromEntries(nodes.map((n) => [n.id, fitLabel(n)]))

  let minX = Infinity
  let minY = Infinity
  let maxX = -Infinity
  let maxY = -Infinity
  for (const n of nodes) {
    const p = positions[n.id]
    if (!p) continue
    const s = fitted[n.id]
    minX = Math.min(minX, p.x - s.w / 2)
    minY = Math.min(minY, p.y - s.h / 2)
    maxX = Math.max(maxX, p.x + s.w / 2)
    maxY = Math.max(maxY, p.y + s.h / 2)
  }
  if (minX === Infinity) return null
  const pad = 40
  const vb = {
    x: Math.min(0, minX) - pad,
    y: Math.min(0, minY) - pad,
    w: Math.max(maxX, 800) - Math.min(0, minX) + pad * 2,
    h: Math.max(maxY, 600) - Math.min(0, minY) + pad * 2,
  }

  const title = data.lecture_title || 'Lecture Mind Map'

  return (
    <div className="print-chapter px-8 py-7">
      <h1 className="text-[21px] font-semibold text-nt tracking-tight mb-1">{title}</h1>
      <p className="text-[11px] text-nt3 mb-6">
        Concept map · Chapter {ch} · {nodes.length} concepts &amp; {edges.length} connections
      </p>

      <svg
        viewBox={`${vb.x} ${vb.y} ${vb.w} ${vb.h}`}
        className="w-full"
        style={{ maxHeight: 560 }}
        role="img"
        aria-label={`Concept map for chapter ${ch}`}
      >
        {edges.map((edge) => {
          const src = positions[edge.source]
          const tgt = positions[edge.target]
          if (!src || !tgt) return null
          return (
            <path
              key={edge.id}
              d={conceptEdgePath(src, tgt)}
              fill="none"
              stroke="var(--color-ns3)"
              strokeWidth={1.2}
              strokeDasharray="4 3"
            />
          )
        })}

        {nodes.map((node) => {
          const p = positions[node.id]
          if (!p) return null
          const s = NODE_STYLE[node.type]
          const size = fitted[node.id]
          const truncated = size.text !== node.label
          return (
            <g key={node.id} transform={`translate(${p.x} ${p.y})`}>
              <rect
                x={-size.w / 2}
                y={-size.h / 2}
                width={size.w}
                height={size.h}
                rx={s.rx}
                fill={s.fill}
                stroke={s.stroke}
                strokeWidth={node.type === 'focus_concept' ? 1.2 : 0}
                strokeOpacity={node.type === 'focus_concept' ? 0.9 : 0}
              />
              <text
                x={0}
                y={0}
                textAnchor="middle"
                dominantBaseline="central"
                fontSize={s.font}
                fontWeight={s.weight}
                fill={s.text}
                style={{ fontFamily: 'inherit' }}
              >
                {size.text}
              </text>
              {truncated && <title>{node.label}</title>}
            </g>
          )
        })}
      </svg>
    </div>
  )
}
