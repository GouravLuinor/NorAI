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
    const focusGapY = Math.min(140, (height - 120) / Math.max(1, focusNodes.length))
    const startFocusY = centerY - ((focusNodes.length - 1) * focusGapY) / 2

    focusNodes.forEach((fn, i) => {
      const fy = startFocusY + i * focusGapY
      const fx = centerX + 260
      positions[fn.id] = { x: fx, y: fy }

      const childEdges = edges.filter((e) => e.source === fn.id)
      const detailGapY = 55
      const startDetailY = fy - ((childEdges.length - 1) * detailGapY) / 2

      childEdges.forEach((edge, j) => {
        positions[edge.target] = {
          x: fx + 280,
          y: startDetailY + j * detailGapY,
        }
      })
    })
  } else {
    const radius = 220
    const angleStep = (2 * Math.PI) / Math.max(1, focusNodes.length)
    focusNodes.forEach((fn, i) => {
      const angle = i * angleStep - Math.PI / 2
      const fx = centerX + radius * Math.cos(angle)
      const fy = centerY + radius * Math.sin(angle)
      positions[fn.id] = { x: fx, y: fy }

      const childEdges = edges.filter((e) => e.source === fn.id)
      childEdges.forEach((edge, j) => {
        const subAngle = angle + (j - (childEdges.length - 1) / 2) * 0.35
        positions[edge.target] = {
          x: fx + 160 * Math.cos(subAngle),
          y: fy + 160 * Math.sin(subAngle),
        }
      })
    })
  }

  detailNodes.forEach((dn, i) => {
    if (!positions[dn.id]) {
      positions[dn.id] = { x: centerX + 500, y: 100 + i * 50 }
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
