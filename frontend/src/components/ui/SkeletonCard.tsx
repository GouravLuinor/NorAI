interface SkeletonCardProps {
  className?: string
  lines?: number
}

export function SkeletonCard({ className = '', lines = 3 }: SkeletonCardProps) {
  return (
    <div className={`bg-ns border border-bdr2 rounded-lg p-5 fold-marks relative shadow-ev1 animate-pulse ${className}`}>
      <div className="flex items-center gap-2 mb-3">
        <div className="w-4 h-4 rounded bg-ns3" />
        <div className="h-4 bg-ns3 rounded w-1/3" />
      </div>
      <div className="space-y-2">
        {Array.from({ length: lines }).map((_, i) => (
          <div
            key={i}
            className={`h-3 bg-ns3 rounded ${
              i === lines - 1 ? 'w-2/3' : i % 2 === 0 ? 'w-full' : 'w-5/6'
            }`}
          />
        ))}
      </div>
    </div>
  )
}

export function NotesSkeleton() {
  return (
    <div className="space-y-4 p-6">
      <div className="h-6 bg-ns3 rounded w-1/2 animate-pulse mb-6" />
      <SkeletonCard lines={4} />
      <SkeletonCard lines={3} />
      <SkeletonCard lines={5} />
    </div>
  )
}

export function QuizSkeleton() {
  return (
    <div className="p-4 space-y-4 animate-pulse">
      <div className="h-4 bg-ns3 rounded w-1/4 mb-2" />
      <div className="h-5 bg-ns3 rounded w-3/4 mb-4" />
      <div className="space-y-2">
        <div className="h-10 bg-ns2 border border-bdr rounded-md" />
        <div className="h-10 bg-ns2 border border-bdr rounded-md" />
        <div className="h-10 bg-ns2 border border-bdr rounded-md" />
      </div>
    </div>
  )
}

export function ConceptSkeleton() {
  return (
    <div className="p-6 grid grid-cols-2 gap-4 animate-pulse">
      <div className="h-32 bg-ns border border-bdr2 rounded-lg" />
      <div className="h-32 bg-ns border border-bdr2 rounded-lg" />
      <div className="h-32 bg-ns border border-bdr2 rounded-lg" />
      <div className="h-32 bg-ns border border-bdr2 rounded-lg" />
    </div>
  )
}
