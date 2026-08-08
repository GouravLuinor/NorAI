import React from 'react'
import { BrowserRouter, Routes, Route, useNavigate } from 'react-router-dom'
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
    <LandingPage
      onStartWorkspace={() => navigate('/app')}
      onOpenPricing={() => navigate('/pricing')}
    />
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
    </BrowserRouter>
  )
}