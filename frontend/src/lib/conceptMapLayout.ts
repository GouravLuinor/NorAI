export interface ConceptNode {
  id: string
  label: string
  type: 'root' | 'focus_concept' | 'detail'
  category: string
  description: string
  x?: number
  y?: number
}

export interface ConceptEdge {
  id: string
  source: string
  target: string
  label: string
}

export interface ConceptMapResponse {
  lecture_title: string
  chapter_id: number
  root: { id: string; label: string; summary: string }
  nodes: ConceptNode[]
  edges: ConceptEdge[]
}

export type ConceptLayoutMode = 'tree' | 'radial'

// Single source of truth for node placement. Both the interactive
// ConceptMapView and the print/interactive exports consume this so the
// on-screen and exported layouts stay in sync.
export function layoutConceptMap(
  nodes: ConceptNode[],
  edges: ConceptEdge[],
  mode: ConceptLayoutMode,
  opts: { height: number }
): Record<string, { x: number; y: number }> {
  const { height } = opts
  const centerX = 220
  const centerY = height / 2

  const rootNode = nodes.find((n) => n.type === 'root') || nodes[0]
  const focusNodes = nodes.filter((n) => n.type === 'focus_concept')
  const detailNodes = nodes.filter((n) => n.type === 'detail')

  const positions: Record<string, { x: number; y: number }> = {}
  if (!rootNode) return positions
  positions[rootNode.id] = { x: centerX, y: centerY }

  if (mode === 'tree') {
    // Vertical budget: each focus concept occupies a band proportional to how
    // many detail children hang off it, so dense maps never overlap. Without
    // this, a fixed detailGapY (55px) exceeds the focus spacing once there are
    // more than a handful of focus nodes and the subtrees collide.
    const childrenOf = (fn: ConceptNode) => edges.filter((e) => e.source === fn.id)
    const weights = focusNodes.map((fn) => Math.max(1, childrenOf(fn).length))
    const totalWeight = weights.reduce((a, b) => a + b, 0) || 1
    // 46px floor keeps node cards from touching; dense maps simply grow taller
    // than the viewport and the existing zoom/pan handles the overflow.
    const bandH = Math.max(46, Math.min(140, (height - 120) / totalWeight))

    let cursorY = centerY - (totalWeight * bandH) / 2
    focusNodes.forEach((fn, i) => {
      const kids = childrenOf(fn)
      const w = weights[i]
      const fx = centerX + 260
      const fy = cursorY + (w * bandH) / 2
      positions[fn.id] = { x: fx, y: fy }

      if (kids.length) {
        const spacing = bandH
        const startY = cursorY + bandH / 2
        kids.forEach((edge, j) => {
          positions[edge.target] = { x: fx + 280, y: startY + j * spacing }
        })
      }
      cursorY += w * bandH
    })
  } else {
    const focusCount = Math.max(1, focusNodes.length)
    const angleStep = (2 * Math.PI) / focusCount
    // Cards are truncated to max-w-[220px] (focus/detail) / max-w-[300px]
    // (root), so layout can bound their widths. Size the ring so (a) a focus
    // card never reaches back over the root card and (b) adjacent focus cards
    // keep clear along the ring.
    const focusHalf = 110 + 16 // max-w-220 / 2 + px-4
    const rootHalf = 150 + 20 // max-w-300 / 2 + px-5
    const gap = 40
    const ringRadius = (220 + gap) / (2 * Math.sin(angleStep / 2))
    const radius = Math.max(rootHalf + focusHalf + gap, ringRadius)
    focusNodes.forEach((fn, i) => {
      const angle = i * angleStep - Math.PI / 2
      const fx = centerX + radius * Math.cos(angle)
      const fy = centerY + radius * Math.sin(angle)
      positions[fn.id] = { x: fx, y: fy }

      // Children cascade outward along the focus ray so siblings of the same
      // focus never collide with each other (collinear) and stay clear of the
      // neighboring focus's subtree (arc separation grows with radius).
      // Spacing must exceed the 220px card width so even a horizontal ray
      // keeps its stack disjoint.
      const childEdges = edges.filter((e) => e.source === fn.id)
      childEdges.forEach((edge, j) => {
        positions[edge.target] = {
          x: fx + (j + 1) * 260 * Math.cos(angle),
          y: fy + (j + 1) * 260 * Math.sin(angle),
        }
      })
    })
  }

  detailNodes.forEach((dn, i) => {
    if (!positions[dn.id]) {
      positions[dn.id] = { x: centerX + 500, y: 80 + i * 46 }
    }
  })

  return positions
}

// Cubic bezier edge path shared by the interactive SVG and the print SVG.
export function conceptEdgePath(
  src: { x: number; y: number },
  tgt: { x: number; y: number }
): string {
  const dx = tgt.x - src.x
  return `M ${src.x} ${src.y} C ${src.x + dx * 0.45} ${src.y}, ${tgt.x - dx * 0.45} ${tgt.y}, ${tgt.x} ${tgt.y}`
}
