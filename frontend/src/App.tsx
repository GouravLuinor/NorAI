import { BrowserRouter, Routes, Route, useNavigate } from 'react-router-dom'
import { MotionConfig } from 'framer-motion'
import { LandingPage } from './pages/LandingPage'
import { PricingPage } from './pages/PricingPage'
import { UploadPage } from './pages/UploadPage'
import { ProcessingPage } from './pages/ProcessingPage'
import { Workspace } from './components/layout/Workspace'
import { PrintPage } from './components/PrintPage'
import { ToastContainer } from './components/ui/ToastContainer'
import { AuthModal } from './components/auth/AuthModal'

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
        <Routes>
          <Route path="/" element={<LandingRouteWrapper />} />
          <Route path="/pricing" element={<PricingRouteWrapper />} />
          <Route path="/app" element={<UploadPage />} />
          <Route path="/process/:taskId" element={<ProcessingPage />} />
          <Route path="/workspace" element={<Workspace />} />
          <Route path="/workspace/:lectureId" element={<Workspace />} />
          <Route path="/print" element={<PrintPage />} />
        </Routes>
      </MotionConfig>
    </BrowserRouter>
  )
}