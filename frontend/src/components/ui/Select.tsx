import { useState, useRef, useEffect, useId, type KeyboardEvent } from 'react'
import { ChevronDown, Check } from 'lucide-react'
import { FOCUS_RING } from './shared'

export interface SelectOption {
  value: string
  label: string
}

interface SelectProps {
  options: SelectOption[]
  value: string
  onChange: (value: string) => void
  ariaLabel?: string
  placeholder?: string
  className?: string
  id?: string
  disabled?: boolean
}

export function Select({
  options,
  value,
  onChange,
  ariaLabel,
  placeholder = 'Select option...',
  className = '',
  id,
  disabled = false,
}: SelectProps) {
  const [isOpen, setIsOpen] = useState(false)
  const [highlightedIndex, setHighlightedIndex] = useState(-1)
  const typeaheadRef = useRef('')
  const typeaheadTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const containerRef = useRef<HTMLDivElement>(null)
  const triggerRef = useRef<HTMLButtonElement>(null)
  const generatedId = useId()
  const listboxId = id ? `${id}-listbox` : `select-${generatedId}-listbox`

  const selectedOption = options.find((opt) => opt.value === value)

  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
        setIsOpen(false)
      }
    }
    document.addEventListener('mousedown', handleClickOutside)
    return () => document.removeEventListener('mousedown', handleClickOutside)
  }, [])

  useEffect(() => () => {
    if (typeaheadTimerRef.current) clearTimeout(typeaheadTimerRef.current)
  }, [])

  useEffect(() => {
    if (isOpen) {
      const idx = options.findIndex((opt) => opt.value === value)
      setHighlightedIndex(idx >= 0 ? idx : 0)
    }
  }, [isOpen, options, value])

  // P4.1: Home/End jump, printable keys typeahead (500ms buffer), Escape
  // returns focus to the trigger.
  const handleTypeahead = (e: KeyboardEvent<HTMLButtonElement>) => {
    typeaheadRef.current += e.key.toLowerCase()
    if (typeaheadTimerRef.current) clearTimeout(typeaheadTimerRef.current)
    typeaheadTimerRef.current = setTimeout(() => {
      typeaheadRef.current = ''
    }, 500)

    const query = typeaheadRef.current
    let start = highlightedIndex + 1
    let match = -1
    for (let i = 0; i < options.length; i++) {
      const idx = (start + i) % options.length
      if (options[idx].label.toLowerCase().startsWith(query)) {
        match = idx
        break
      }
    }
    if (match === -1 && query.length > 1) {
      for (let i = 0; i < options.length; i++) {
        if (options[i].label.toLowerCase().startsWith(query[0])) {
          match = i
          break
        }
      }
    }
    if (match !== -1) setHighlightedIndex(match)
  }

  const handleKeyDown = (e: KeyboardEvent<HTMLButtonElement>) => {
    if (disabled) return
    if (!isOpen) {
      if (['ArrowDown', 'ArrowUp', 'Enter', ' '].includes(e.key)) {
        e.preventDefault()
        setIsOpen(true)
      } else if (e.key.length === 1 && !e.metaKey && !e.ctrlKey && !e.altKey) {
        setIsOpen(true)
        handleTypeahead(e)
      }
      return
    }

    switch (e.key) {
      case 'ArrowDown':
        e.preventDefault()
        setHighlightedIndex((prev) => (prev + 1) % options.length)
        break
      case 'ArrowUp':
        e.preventDefault()
        setHighlightedIndex((prev) => (prev - 1 + options.length) % options.length)
        break
      case 'Home':
        e.preventDefault()
        setHighlightedIndex(0)
        break
      case 'End':
        e.preventDefault()
        setHighlightedIndex(options.length - 1)
        break
      case 'Enter':
      case ' ':
        e.preventDefault()
        if (highlightedIndex >= 0 && highlightedIndex < options.length) {
          onChange(options[highlightedIndex].value)
          setIsOpen(false)
        }
        break
      case 'Escape':
        e.preventDefault()
        setIsOpen(false)
        triggerRef.current?.focus()
        break
      default:
        if (e.key.length === 1 && !e.metaKey && !e.ctrlKey && !e.altKey) {
          handleTypeahead(e)
        }
    }
  }

  return (
    <div ref={containerRef} className={`relative w-full ${className}`}>
      <button
        ref={triggerRef}
        type="button"
        role="combobox"
        id={id}
        disabled={disabled}
        aria-expanded={isOpen}
        aria-haspopup="listbox"
        aria-controls={isOpen ? listboxId : undefined}
        aria-activedescendant={isOpen && highlightedIndex >= 0 ? `${listboxId}-option-${highlightedIndex}` : undefined}
        aria-label={ariaLabel}
        onClick={() => setIsOpen((prev) => !prev)}
        onKeyDown={handleKeyDown}
        className={`w-full flex items-center justify-between gap-1.5 bg-nb border border-bdr2 rounded-md px-2.5 py-1.5 text-11 text-nt hover:border-nt4 transition cursor-pointer disabled:opacity-60 disabled:cursor-not-allowed disabled:pointer-events-none ${FOCUS_RING}`}
      >
        <span className="truncate">{selectedOption ? selectedOption.label : placeholder}</span>
        <ChevronDown
          size={12}
          strokeWidth={1.5}
          className={`text-nt3 shrink-0 transition-transform duration-150 ${isOpen ? 'rotate-180' : ''}`}
        />
      </button>

      {isOpen && (
        <ul
          role="listbox"
          id={listboxId}
          aria-label={ariaLabel}
          className="absolute left-0 right-0 top-full mt-1 z-50 bg-ns border border-bdr2 rounded-md py-1 shadow-ev2 max-h-48 overflow-y-auto"
        >
          {options.map((opt, idx) => {
            const isSelected = opt.value === value
            const isHighlighted = idx === highlightedIndex
            return (
              <li
                key={opt.value}
                id={`${listboxId}-option-${idx}`}
                role="option"
                aria-selected={isSelected}
                onClick={() => {
                  onChange(opt.value)
                  setIsOpen(false)
                }}
                onMouseEnter={() => setHighlightedIndex(idx)}
                className={`flex items-center justify-between px-2.5 py-1.5 text-11 cursor-pointer transition ${
                  isSelected
                    ? 'bg-npb text-nt font-medium'
                    : isHighlighted
                    ? 'bg-ns2 text-nt2'
                    : 'text-nt3 hover:bg-ns2 hover:text-nt2'
                }`}
              >
                <span className="truncate">{opt.label}</span>
                {isSelected && <Check size={11} strokeWidth={2} className="text-np shrink-0 ml-1.5" />}
              </li>
            )
          })}
        </ul>
      )}
    </div>
  )
}
