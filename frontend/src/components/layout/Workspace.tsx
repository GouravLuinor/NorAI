import { Sidebar } from './Sidebar'
import { DocPanel } from './DocPanel'
import { AIPanel } from './AIPanel'

export function Workspace() {
  return (
    <div
      className="workspace grid h-screen bg-nb text-nt text-xs font-sans rounded-xl border border-bdr2 overflow-hidden shadow-2xl"
      style={{
        gridTemplateColumns: 'var(--sidebar-width, 220px) 1fr 268px',
        transition: 'grid-template-columns 240ms cubic-bezier(0.4,0,0.2,1)',
      }}
    >
      <Sidebar />
      <DocPanel />
      <AIPanel />
    </div>
  )
}