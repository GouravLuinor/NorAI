import { useState, useRef, useEffect, useCallback } from 'react'
import { Search, X, ChevronUp, ChevronDown } from 'lucide-react'
import { IconButton } from '../ui/IconButton'
import { Input } from '../ui/Input'

interface SearchBarProps {
  isOpen: boolean
  onClose: () => void
}

export function SearchBar({ isOpen, onClose }: SearchBarProps) {
  const [query, setQuery] = useState('')
  const [matchCount, setMatchCount] = useState(0)
  const [currentMatch, setCurrentMatch] = useState(0)
  const inputRef = useRef<HTMLInputElement>(null)
  const marksRef = useRef<HTMLElement[]>([])

  // Container we search inside
  const getContainer = () => document.querySelector('.doc-content') as HTMLElement | null

  // Remove all highlights and restore original text
  const clearHighlights = useCallback(() => {
    marksRef.current.forEach(mark => {
      const parent = mark.parentNode
      if (parent) {
        parent.replaceChild(document.createTextNode(mark.textContent || ''), mark)
        parent.normalize()
      }
    })
    marksRef.current = []
  }, [])

  // Search and highlight
  const performSearch = useCallback((q: string) => {
    clearHighlights()
    if (!q.trim()) {
      setMatchCount(0)
      setCurrentMatch(0)
      return
    }

    const container = getContainer()
    if (!container) return

    const regex = new RegExp(q.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'), 'gi')
    const walker = document.createTreeWalker(container, NodeFilter.SHOW_TEXT, null)

    const textNodes: Text[] = []
    while (walker.nextNode()) {
      textNodes.push(walker.currentNode as Text)
    }

    const newMarks: HTMLElement[] = []
    textNodes.forEach(node => {
      const text = node.textContent || ''
      if (!regex.test(text)) return
      regex.lastIndex = 0  // reset

      const fragment = document.createDocumentFragment()
      let lastIndex = 0
      let match
      while ((match = regex.exec(text)) !== null) {
        // Text before match
        if (match.index > lastIndex) {
          fragment.appendChild(document.createTextNode(text.slice(lastIndex, match.index)))
        }
        // Highlighted match
        const mark = document.createElement('mark')
        mark.textContent = match[0]
        mark.className = 'bg-np/30 text-nt rounded-sm'
        mark.dataset.searchMatch = 'true'
        fragment.appendChild(mark)
        newMarks.push(mark)
        lastIndex = regex.lastIndex
        if (match[0].length === 0) regex.lastIndex++  // avoid infinite loop on zero-length matches
      }
      // Remaining text
      if (lastIndex < text.length) {
        fragment.appendChild(document.createTextNode(text.slice(lastIndex)))
      }
      node.parentNode?.replaceChild(fragment, node)
    })

    marksRef.current = newMarks
    setMatchCount(newMarks.length)
    setCurrentMatch(newMarks.length > 0 ? 1 : 0)
    if (newMarks.length > 0) {
      newMarks[0].scrollIntoView({ behavior: 'smooth', block: 'center' })
    }
  }, [clearHighlights])

  // Navigate to a specific match
  const goToMatch = useCallback((index: number) => {
    if (marksRef.current.length === 0) return
    // Reset current highlight
    marksRef.current.forEach(m => m.classList.remove('!bg-npf', '!text-npfg', 'ring-2', 'ring-np'))
    const i = ((index - 1) % marksRef.current.length + marksRef.current.length) % marksRef.current.length
    const mark = marksRef.current[i]
    mark.classList.add('!bg-npf', '!text-npfg', 'ring-2', 'ring-np')
    mark.scrollIntoView({ behavior: 'smooth', block: 'center' })
    setCurrentMatch(i + 1)
  }, [])

  // Handle keyboard shortcuts
  useEffect(() => {
    if (!isOpen) return
    const handler = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        clearHighlights()
        onClose()
      } else if (e.key === 'Enter') {
        e.preventDefault()
        if (e.shiftKey) goToMatch(currentMatch - 1)
        else goToMatch(currentMatch + 1)
      }
    }
    window.addEventListener('keydown', handler)
    return () => window.removeEventListener('keydown', handler)
  }, [isOpen, currentMatch, goToMatch, clearHighlights, onClose])

  // Focus input when opened
  useEffect(() => {
    if (isOpen) inputRef.current?.focus()
  }, [isOpen])

  // Search on query change
  useEffect(() => {
    performSearch(query)
  }, [query, performSearch])

  if (!isOpen) return null

  return (
    <div className="flex items-center gap-1 ml-2">
      <div className="flex items-center gap-1 bg-nb border border-bdr2 rounded-md px-2 py-0.5 focus-within:shadow-[0_0_0_1px_var(--color-np)] transition">
        <Search size={11} strokeWidth={1.5} className="text-nt3" />
        <Input
          ref={inputRef}
          type="text"
          value={query}
          onChange={e => setQuery(e.target.value)}
          placeholder="Find in document…"
          className="text-2xs placeholder:text-nt4 w-32"
        />
        {matchCount > 0 && (
          <span className="text-3xs text-nt3 whitespace-nowrap">
            {currentMatch}/{matchCount}
          </span>
        )}
        <IconButton label="Previous match" variant="bare" onClick={() => goToMatch(currentMatch - 1)}>
          <ChevronUp size={11} strokeWidth={1.5} />
        </IconButton>
        <IconButton label="Next match" variant="bare" onClick={() => goToMatch(currentMatch + 1)}>
          <ChevronDown size={11} strokeWidth={1.5} />
        </IconButton>
      </div>
      <IconButton label="Close search" variant="bare" onClick={() => { clearHighlights(); onClose() }}>
        <X size={12} strokeWidth={1.5} />
      </IconButton>
    </div>
  )
}