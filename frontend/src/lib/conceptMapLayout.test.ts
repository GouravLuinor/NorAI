import { describe, expect, it } from 'vitest'
import { conceptEdgePath, layoutConceptMap } from './conceptMapLayout'
import type { ConceptNode, ConceptEdge } from './conceptMapLayout'

function node(id: string, type: ConceptNode['type']): ConceptNode {
  return { id, label: id, type, category: '', description: '' }
}

function edge(source: string, target: string): ConceptEdge {
  return { id: `${source}-${target}`, source, target, label: '' }
}

describe('layoutConceptMap', () => {
  it('returns an empty map for no nodes', () => {
    expect(layoutConceptMap([], [], 'tree', { height: 600 })).toEqual({})
  })

  it('places the root at the vertical center', () => {
    const nodes = [node('root', 'root')]
    expect(layoutConceptMap(nodes, [], 'tree', { height: 600 })).toEqual({ root: { x: 220, y: 300 } })
  })

  it('tree mode fans focus concepts vertically and children to the right', () => {
    const nodes = [node('root', 'root'), node('a', 'focus_concept'), node('b', 'focus_concept'), node('d', 'detail')]
    const edges = [edge('root', 'a'), edge('root', 'b'), edge('a', 'd')]
    const pos = layoutConceptMap(nodes, edges, 'tree', { height: 600 })
    expect(pos['a'].y).not.toBe(pos['b'].y)
    expect(pos['a'].x).toBeGreaterThan(pos['root'].x)
    expect(pos['d'].x).toBeGreaterThan(pos['a'].x)
  })

  it('radial mode keeps focus concepts within radius bounds', () => {
    const nodes = [
      node('root', 'root'),
      node('a', 'focus_concept'),
      node('b', 'focus_concept'),
      node('c', 'focus_concept'),
    ]
    const edges = [edge('root', 'a'), edge('root', 'b'), edge('root', 'c')]
    const pos = layoutConceptMap(nodes, edges, 'radial', { height: 600 })
    expect(pos['root']).toEqual({ x: 220, y: 300 })
    for (const p of Object.values(pos)) {
      expect(p.x).toBeGreaterThanOrEqual(0)
      expect(p.y).toBeGreaterThanOrEqual(0)
    }
  })

  it('is deterministic for identical inputs', () => {
    const nodes = [node('root', 'root'), node('a', 'focus_concept'), node('d', 'detail')]
    const edges = [edge('root', 'a'), edge('a', 'd')]
    const a = layoutConceptMap(nodes, edges, 'radial', { height: 800 })
    const b = layoutConceptMap(nodes, edges, 'radial', { height: 800 })
    expect(a).toEqual(b)
  })
})

describe('conceptEdgePath', () => {
  it('emits a cubic bezier path', () => {
    const path = conceptEdgePath({ x: 0, y: 0 }, { x: 100, y: 0 })
    expect(path).toMatch(/^M 0 0 C/)
    expect(path).toContain('100 0')
  })
})
