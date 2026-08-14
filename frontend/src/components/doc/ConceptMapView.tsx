import { useState, useEffect, useRef, useCallback } from 'react'
import { motion } from 'framer-motion'
import { ZoomIn, ZoomOut, Maximize2, Sparkles, MessageSquare, Compass, X } from 'lucide-react'
import { useLectureStore } from '../../stores/useLectureStore'
import { Button } from '../ui/Button'
import { Badge } from '../ui/Badge'
import { useToastStore } from '../../stores/useToastStore'
import { useThreadStore } from '../../stores/useThreadStore'
import { useQuizStore } from '../../stores/useQuizStore'
import { sendChatMessageStream } from '../../lib/chatApi'
import { apiGet } from '../../lib/http'
import { buildReferences } from '../../lib/references'
import { ConceptSkeleton } from '../ui/SkeletonCard'
import {
  layoutConceptMap,
  conceptEdgePath,
  type ConceptNode,
  type ConceptEdge,
  type ConceptMapResponse,
  type ConceptLayoutMode,
} from '../../lib/conceptMapLayout'

export type { ConceptNode, ConceptEdge, ConceptMapResponse }

const stripSources = (text: string) => text.replace(/\*\*Sources\*\*[\s\S]*$/, '').trim()

interface ConceptMapViewProps {
  chapterId: number
}

export function ConceptMapView({ chapterId }: ConceptMapViewProps) {
  const lectureId = useLectureStore((s) => s.activeLectureId) || 'default'
  const addToast = useToastStore((s) => s.addToast)
  const addMessage = useThreadStore((s) => s.addMessage)
  
  const [data, setData] = useState<ConceptMapResponse | null>(null)
  const [loading, setLoading] = useState(true)
  const [selectedNode, setSelectedNode] = useState<ConceptNode | null>(null)
  const [zoom, setZoom] = useState(1)
  const [pan, setPan] = useState({ x: 0, y: 0 })
  const [isDragging, setIsDragging] = useState(false)
  const [dragStart, setDragStart] = useState({ x: 0, y: 0 })
  const [layoutMode, setLayoutMode] = useState<ConceptLayoutMode>('tree')

  const containerRef = useRef<HTMLDivElement>(null)
  const askInFlightRef = useRef(false)

  const genId = () => `msg-${Date.now()}-${Math.random().toString(36).slice(2, 9)}`

  const handleAskNora = useCallback(async (conceptLabel: string) => {
    if (askInFlightRef.current) return
    askInFlightRef.current = true

    const text = `Explain the concept "${conceptLabel}" from Chapter ${chapterId} in detail with examples.`
    const userMsg = {
      id: genId(),
      role: 'user' as const,
      content: text,
      timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
    }
    
    // 1. Add user message and switch to Tutor mode
    addMessage(userMsg)
    useQuizStore.getState().setMode('tutor')

    // 2. Stream response from backend Gemini API
    const storeState = useThreadStore.getState()
    const targetThreadId = storeState.threadId || 'default'
    storeState.setLoading(true)

    let acc = ''
    try {
      for await (const chunk of sendChatMessageStream(
        targetThreadId,
        text,
        '',
        undefined,
        { messageId: userMsg.id }
      )) {
        if (typeof chunk === 'string') {
          acc += chunk
          useThreadStore.getState().setStreamingText(stripSources(acc))
        } else if (chunk?.data) {
          useThreadStore.getState().setStreamingText('')
          const cleanAnswer = stripSources(acc) || 'Here is the detailed explanation for this concept.'
          const assistantMsg = {
            id: chunk.data.assistant_message_id || genId(),
            role: 'assistant' as const,
            content: cleanAnswer,
            timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
          }

          // RC-FIX2: Atomic read-check-write — same guard as ChatArea/HighlightAsk.
          // If loadThreadMessages already injected this response from the backend
          // checkpoint, skip the append to avoid duplicates.
          useThreadStore.setState((s) => {
            const currentMessages = s.threadId === targetThreadId
              ? s.messages
              : (s._messagesCache[targetThreadId] ?? [])
            if (currentMessages.some(m => m.role === 'assistant' && m.content === cleanAnswer)) {
              return {}
            }
            const updated = [...currentMessages, assistantMsg]
            return {
              _messagesCache: { ...s._messagesCache, [targetThreadId]: updated },
              ...(s.threadId === targetThreadId ? { messages: updated } : {}),
            }
          })

          useThreadStore.getState().setLiveReferences(
            buildReferences(chunk.data.retrieved_chunks ?? [], chunk.data.retrieved_images ?? [], '', chunk.data.verified_citations ?? [])
          )
        }
      }
    } catch (err) {
      console.error('Failed to stream Nora response:', err)
    } finally {
      useThreadStore.getState().setLoading(false)
      useThreadStore.getState().setStreamingText('')
      askInFlightRef.current = false
    }

    addToast(`Asked Nora about "${conceptLabel}"`, 'success')
  }, [chapterId, addMessage, addToast])

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    apiGet<ConceptMapResponse>(`/concept-map?chapter_id=${chapterId}&lecture_id=${lectureId}`)
      .then((resData) => {
        if (cancelled) return
        setData(resData)
        if (resData.nodes && resData.nodes.length > 0) {
          setSelectedNode(resData.nodes[0])
        }
        setLoading(false)
      })
      .catch(() => {
        if (!cancelled) {
          setData(null)
          setLoading(false)
        }
      })
    return () => {
      cancelled = true
    }
  }, [chapterId, lectureId])

  if (loading) {
    return <ConceptSkeleton />
  }

  if (!data || !data.nodes || data.nodes.length === 0) {
    return (
      <div className="flex-1 flex flex-col items-center justify-center text-nt3 text-sm p-8 text-center gap-2">
        <Compass className="w-8 h-8 opacity-40 mb-2" />
        <p className="font-semibold text-nt">Concept Map not available</p>
        <p className="text-xs text-nt3">No concepts derived for Chapter {chapterId}.</p>
      </div>
    )
  }

  // Calculate layout coordinates for nodes via the shared layout engine
  const nodePositions = layoutConceptMap(data.nodes, data.edges, layoutMode, { height: 600 })

  // Drag handlers
  const handleMouseDown = (e: React.MouseEvent) => {
    if ((e.target as HTMLElement).tagName === 'button' || (e.target as HTMLElement).closest('.concept-card')) return
    setIsDragging(true)
    setDragStart({ x: e.clientX - pan.x, y: e.clientY - pan.y })
  }

  const handleMouseMove = (e: React.MouseEvent) => {
    if (!isDragging) return
    setPan({ x: e.clientX - dragStart.x, y: e.clientY - dragStart.y })
  }

  const handleMouseUp = () => setIsDragging(false)

  return (
    <div className="flex flex-col h-full bg-nb relative overflow-hidden select-none">
      {/* Top Header Controls */}
      <div className="flex items-center justify-between px-6 py-3 border-b border-bdr bg-ns shrink-0">
        <div>
          <h2 className="text-sm font-semibold text-nt tracking-tight flex items-center gap-2">
            <Sparkles size={14} className="text-np" /> Ch {String(chapterId).padStart(2, '0')} Concept Map
          </h2>
          <p className="text-2xs text-nt3">
            Derived from lecture outline & section notes · {data.nodes.length} concepts & connections
          </p>
        </div>

        <div className="flex items-center gap-2">
          <div className="flex items-center gap-1 p-0.5 rounded-md bg-ns2 border border-bdr2">
            <button
              type="button"
              onClick={() => setLayoutMode('tree')}
              className={`px-2.5 py-1 rounded-[5px] text-2xs font-medium transition ${
                layoutMode === 'tree' ? 'bg-np text-ns shadow-sm' : 'text-nt3 hover:text-nt2'
              }`}
            >
              Tree Layout
            </button>
            <button
              type="button"
              onClick={() => setLayoutMode('radial')}
              className={`px-2.5 py-1 rounded-[5px] text-2xs font-medium transition ${
                layoutMode === 'radial' ? 'bg-np text-ns shadow-sm' : 'text-nt3 hover:text-nt2'
              }`}
            >
              Radial
            </button>
          </div>

          <div className="flex items-center gap-1 bg-ns2 p-0.5 rounded-md border border-bdr2">
            <Button
              variant="outline"
              onClick={() => setZoom((z) => Math.min(z + 0.15, 2.5))}
              className="p-1 rounded-sm text-2xs h-7 w-7"
            >
              <ZoomIn size={13} />
            </Button>
            <Button
              variant="outline"
              onClick={() => setZoom((z) => Math.max(z - 0.15, 0.4))}
              className="p-1 rounded-sm text-2xs h-7 w-7"
            >
              <ZoomOut size={13} />
            </Button>
            <Button
              variant="outline"
              onClick={() => {
                setZoom(1)
                setPan({ x: 0, y: 0 })
              }}
              className="p-1 rounded-sm text-2xs h-7 w-7"
            >
              <Maximize2 size={13} />
            </Button>
          </div>
        </div>
      </div>

      {/* Main Canvas Area */}
      <div
        ref={containerRef}
        className="flex-1 relative cursor-grab active:cursor-grabbing overflow-hidden bg-dot-grid"
        onMouseDown={handleMouseDown}
        onMouseMove={handleMouseMove}
        onMouseUp={handleMouseUp}
        onMouseLeave={handleMouseUp}
      >
        <svg
          className="w-full h-full absolute inset-0 pointer-events-none"
          style={{
            transform: `translate(${pan.x}px, ${pan.y}px) scale(${zoom})`,
            transformOrigin: 'top left',
            transition: isDragging ? 'none' : 'transform 0.15s ease-out',
          }}
        >
          <defs>
            <linearGradient id="edge-grad" x1="0%" y1="0%" x2="100%" y2="0%">
              <stop offset="0%" stopColor="var(--color-np)" stopOpacity="0.8" />
              <stop offset="100%" stopColor="var(--color-ns3)" stopOpacity="0.4" />
            </linearGradient>
          </defs>

          {/* Render Connection Paths */}
          {data.edges.map((edge) => {
            const src = nodePositions[edge.source]
            const tgt = nodePositions[edge.target]
            if (!src || !tgt) return null

            const isSelected = selectedNode && (selectedNode.id === edge.source || selectedNode.id === edge.target)

            // Smooth cubic bezier curve path
            const pathD = conceptEdgePath(src, tgt)

            return (
              <g key={edge.id}>
                <path
                  d={pathD}
                  fill="none"
                  stroke={isSelected ? 'var(--color-np)' : 'url(#edge-grad)'}
                  strokeWidth={isSelected ? 2.5 : 1.5}
                  strokeDasharray={isSelected ? 'none' : '4, 4'}
                  className="transition-all duration-200"
                />
              </g>
            )
          })}
        </svg>

        {/* Render Interactive Nodes */}
        <div
          className="absolute inset-0 pointer-events-none"
          style={{
            transform: `translate(${pan.x}px, ${pan.y}px) scale(${zoom})`,
            transformOrigin: 'top left',
            transition: isDragging ? 'none' : 'transform 0.15s ease-out',
          }}
        >
          {data.nodes.map((node) => {
            const pos = nodePositions[node.id] || { x: 100, y: 100 }
            const isSelected = selectedNode?.id === node.id

            const isRoot = node.type === 'root'
            const isFocus = node.type === 'focus_concept'

            return (
              <div
                key={node.id}
                onClick={() => setSelectedNode(node)}
                style={{
                  left: `${pos.x}px`,
                  top: `${pos.y}px`,
                  transform: 'translate(-50%, -50%)',
                }}
                className={`absolute pointer-events-auto cursor-pointer transition-all duration-200 ${
                  isRoot
                    ? 'px-5 py-3 rounded-full bg-np text-ns font-bold text-sm shadow-lg border-2 border-ns3 hover:scale-105'
                    : isFocus
                    ? `px-4 py-2.5 rounded-xl border font-semibold text-xs shadow-ev1 ${
                        isSelected
                          ? 'bg-ns2 border-np text-nt shadow-md scale-105 ring-2 ring-np/30'
                          : 'bg-nb border-bdr2 text-nt hover:border-np/50'
                      }`
                    : `px-3.5 py-1.5 rounded-lg border text-2xs font-medium ${
                        isSelected
                          ? 'bg-ns2 border-np text-nt ring-1 ring-np/30'
                          : 'bg-ns border-bdr text-nt2 hover:border-bdr2'
                      }`
                }`}
              >
                <div className="flex items-center gap-2 whitespace-nowrap">
                  {isRoot && <Sparkles size={14} className="shrink-0" />}
                  <span>{node.label}</span>
                </div>
              </div>
            )
          })}
        </div>

        {/* Selected Concept Floating Detail Modal */}
        {selectedNode && (
          <motion.div
            drag
            dragConstraints={containerRef}
            dragElastic={0.1}
            dragMomentum={false}
            className="concept-card absolute right-6 top-6 cursor-grab active:cursor-grabbing w-80 bg-ns/95 backdrop-blur-md border border-bdr2 rounded-xl p-5 shadow-ev3 pointer-events-auto space-y-3 z-20"
          >
            <div className="flex items-start justify-between">
              <div className="space-y-1">
                <Badge tone="ns" className="text-3xs uppercase tracking-wider font-mono">
                  {selectedNode.category || 'Concept'}
                </Badge>
                <h3 className="text-sm font-semibold text-nt leading-tight">{selectedNode.label}</h3>
              </div>
              <button
                type="button"
                onClick={() => setSelectedNode(null)}
                className="text-nt3 hover:text-nt transition p-1"
              >
                <X size={14} />
              </button>
            </div>

            <p className="text-xs text-nt2 leading-relaxed border-t border-bdr pt-3">
              {selectedNode.description || `Concept from Chapter ${chapterId}`}
            </p>

            <div className="pt-2">
              <Button
                variant="primary"
                onClick={() => handleAskNora(selectedNode.label)}
                className="w-full gap-2 text-xs py-2 rounded-lg"
              >
                <MessageSquare size={13} /> Ask Nora about this
              </Button>
            </div>
          </motion.div>
        )}
      </div>
    </div>
  )
}
