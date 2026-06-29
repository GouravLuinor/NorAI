export function ShimmerLoader() {
  return (
    <div className="flex flex-col gap-2 w-full max-w-[180px] pt-1">
      <div className="h-2.5 rounded-sm bg-gradient-to-r from-ns2 via-ns3 to-ns2 bg-[length:200%_100%] animate-shimmer" />
      <div className="h-2.5 rounded-sm bg-gradient-to-r from-ns2 via-ns3 to-ns2 bg-[length:200%_100%] animate-shimmer w-3/4" />
      <div className="h-2.5 rounded-sm bg-gradient-to-r from-ns2 via-ns3 to-ns2 bg-[length:200%_100%] animate-shimmer w-1/2" />
    </div>
  )
}