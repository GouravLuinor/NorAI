// Deterministic section-card classifier for the print pipeline. Mirrors the
// section_type tags the backend emits; body heuristics cover raw markdown.
const DEFINITION_KEYWORDS = ['core concept', 'core idea', 'key concept', 'detailed explanation', 'explanation', 'interval decomposition', 'full binary tree', 'node structure', 'tree construction', 'query operation', 'update operation', 'recursive', 'introduction', 'motivation', 'overview', 'definition', 'property', 'structure', 'implementation', 'complexity', 'mechanism', 'algorithm']
const CALLOUT_KEYWORDS = ['important observation', 'key insight', 'observation', 'common mistake', 'mistake', 'pitfall', 'efficiency gap', 'dynamic limitation', 'limitation', 'the balance', 'balance', 'trade-off', 'tradeoff', 'caution', 'warning', 'note']
const LIST_KEYWORDS = ['application', 'use case', 'key takeaway', 'takeaway', 'example', 'summary', 'checklist']

export type PrintSectionType = 'code' | 'table' | 'definition' | 'callout' | 'list' | 'prose'

export function getCardType(h: string, body: string): PrintSectionType {
  if (body.includes('```')) return 'code'
  if (body.split('\n').some(l => (l.match(/\|/g) ?? []).length >= 2)) return 'table'
  const hh = h.toLowerCase()
  if (DEFINITION_KEYWORDS.some(k => hh.includes(k))) return 'definition'
  if (CALLOUT_KEYWORDS.some(k => hh.includes(k))) return 'callout'
  if (LIST_KEYWORDS.some(k => hh.includes(k))) return 'list'
  const lines = body.split('\n').filter(l => l.trim())
  if (lines.length > 0 && lines.filter(l => /^\s*[-*•]\s/.test(l)).length / lines.length > 0.5) return 'list'
  return 'prose'
}
