import { lazy, Suspense } from 'react'
import { BrowserRouter, Routes, Route, useNavigate } from 'react-router-dom'
import { MotionConfig } from 'framer-motion'
import { ToastContainer } from './components/ui/ToastContainer'
import { AuthModal } from './components/auth/AuthModal'
import { AppErrorBoundary } from './components/AppErrorBoundary'

// Route-level code-splitting (P5.6): each page ships in its own chunk so the
// marketing routes never pull in the workspace/print stack (KaTeX, highlight,
// doc views).
const LandingPage = lazy(() => import('./pages/LandingPage').then(m => ({ default: m.LandingPage })))
const PricingPage = lazy(() => import('./pages/PricingPage').then(m => ({ default: m.PricingPage })))
const BillingPage = lazy(() => import('./pages/BillingPage').then(m => ({ default: m.BillingPage })))
const UsagePage = lazy(() => import('./pages/UsagePage').then(m => ({ default: m.UsagePage })))
const UploadPage = lazy(() => import('./pages/UploadPage').then(m => ({ default: m.UploadPage })))
const ProcessingPage = lazy(() => import('./pages/ProcessingPage').then(m => ({ default: m.ProcessingPage })))
const Workspace = lazy(() => import('./components/layout/Workspace').then(m => ({ default: m.Workspace })))
const PrintPage = lazy(() => import('./components/PrintPage').then(m => ({ default: m.PrintPage })))

function RouteFallback() {
  return (
    <div className="min-h-screen bg-nb text-nt3 flex items-center justify-center">
      <div className="flex items-center gap-2 text-xs">
        <span className="h-3.5 w-3.5 rounded-full border-2 border-ns3 border-t-np animate-spin" />
        Loading…
      </div>
    </div>
  )
}

function LandingRouteWrapper() {
  const navigate = useNavigate()
  return (
    <LandingPage onStartWorkspace={() => navigate('/app')} />
  )
}

function PricingRouteWrapper() {
  const navigate = useNavigate()
  return (
    <PricingPage
      onStartWorkspace={() => navigate('/app')}
    />
  )
}

export default function App() {
  return (
    <AppErrorBoundary>
      <BrowserRouter>
        <MotionConfig reducedMotion="user">
          <a
            href="#main"
            className="sr-only focus:not-sr-only focus:fixed focus:top-2 focus:left-2 focus:z-50 focus:bg-np focus:text-npfg focus:px-4 focus:py-2 focus:rounded-md focus:shadow-bp"
          >
            Skip to main content
          </a>
          <ToastContainer />
          <AuthModal />
          <Suspense fallback={<RouteFallback />}>
            <Routes>
              <Route path="/" element={<LandingRouteWrapper />} />
              <Route path="/pricing" element={<PricingRouteWrapper />} />
              <Route path="/billing" element={<BillingPage />} />
              <Route path="/usage" element={<UsagePage />} />
              <Route path="/app" element={<UploadPage />} />
              <Route path="/process/:taskId" element={<ProcessingPage />} />
              <Route path="/workspace" element={<Workspace />} />
              <Route path="/workspace/:lectureId" element={<Workspace />} />
              <Route path="/print" element={<PrintPage />} />
            </Routes>
          </Suspense>
        </MotionConfig>
      </BrowserRouter>
    </AppErrorBoundary>
  )
}