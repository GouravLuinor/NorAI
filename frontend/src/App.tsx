import { lazy, Suspense, useEffect } from 'react'
import { BrowserRouter, Routes, Route, useNavigate, useParams, Navigate } from 'react-router-dom'
import { ToastContainer } from './components/ui/ToastContainer'
import { AppErrorBoundary } from './components/AppErrorBoundary'
import { ProtectedRoute } from './components/auth/ProtectedRoute'
import { RateLimitBanner } from './components/ui/RateLimitBanner'
import { ENABLE_PAYMENTS, DEMO_LECTURE_IDS } from './config/features'
import { useAuthStore } from './stores/useAuthStore'
import { useRateLimitStore } from './stores/useRateLimitStore'

// Route-level code-splitting (P5.6)
const MotionProvider = lazy(() =>
  import('./components/ui/MotionProvider').then(m => ({ default: m.MotionProvider })),
)
const AuthModal = lazy(() =>
  import('./components/auth/AuthModal').then(m => ({ default: m.AuthModal })),
)
const AuthPage = lazy(() => import('./pages/AuthPage').then(m => ({ default: m.AuthPage })))
const LandingPage = lazy(() => import('./pages/LandingPage').then(m => ({ default: m.LandingPage })))
const PricingPage = lazy(() => import('./pages/PricingPage').then(m => ({ default: m.PricingPage })))
const BillingPage = lazy(() => import('./pages/BillingPage').then(m => ({ default: m.BillingPage })))
const UsagePage = lazy(() => import('./pages/UsagePage').then(m => ({ default: m.UsagePage })))
const UploadPage = lazy(() => import('./pages/UploadPage').then(m => ({ default: m.UploadPage })))
const ProcessingPage = lazy(() => import('./pages/ProcessingPage').then(m => ({ default: m.ProcessingPage })))
const CoursesPage = lazy(() => import('./pages/CoursesPage').then(m => ({ default: m.CoursesPage })))
const ShareRedirect = lazy(() => import('./pages/ShareRedirect').then(m => ({ default: m.ShareRedirect })))
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
  return <LandingPage onStartWorkspace={() => navigate('/app')} />
}

function PricingRouteWrapper() {
  const navigate = useNavigate()
  return <PricingPage onStartWorkspace={() => navigate('/app')} />
}

function AuthModalBridge() {
  const navigate = useNavigate()
  return <AuthModal onSuccess={() => navigate('/app')} />
}

function WorkspaceRouteWrapper() {
  const { lectureId } = useParams<{ lectureId?: string }>()
  const isDemo = lectureId && DEMO_LECTURE_IDS.includes(lectureId)

  // Demo lectures can be viewed unauthenticated (AI Tutor in AIPanel remains locked)
  if (isDemo) {
    return <Workspace />
  }

  // All user-created lectures require authenticated session
  return (
    <ProtectedRoute>
      <Workspace />
    </ProtectedRoute>
  )
}

export default function App() {
  const initAuth = useAuthStore(s => s.initAuth)
  const checkSystemStatus = useRateLimitStore(s => s.checkSystemStatus)

  useEffect(() => {
    void initAuth()
    void checkSystemStatus()
  }, [initAuth, checkSystemStatus])

  return (
    <AppErrorBoundary>
      <BrowserRouter>
        <Suspense fallback={null}>
          <MotionProvider>
            <a
              href="#main"
              className="sr-only focus:not-sr-only focus:fixed focus:top-2 focus:left-2 focus:z-50 focus:bg-np focus:text-npfg focus:px-4 focus:py-2 focus:rounded-md focus:shadow-bp"
            >
              Skip to main content
            </a>
            <RateLimitBanner />
            <ToastContainer />
            <AuthModalBridge />
            <Suspense fallback={<RouteFallback />}>
              <Routes>
                <Route path="/" element={<LandingRouteWrapper />} />
                <Route path="/login" element={<AuthPage defaultMode="login" />} />
                <Route path="/signup" element={<AuthPage defaultMode="signup" />} />

                {/* Soft-disable billing & pricing when payments are off */}
                <Route
                  path="/pricing"
                  element={ENABLE_PAYMENTS ? <PricingRouteWrapper /> : <Navigate to="/app" replace />}
                />
                <Route
                  path="/billing"
                  element={
                    ENABLE_PAYMENTS ? (
                      <ProtectedRoute>
                        <BillingPage />
                      </ProtectedRoute>
                    ) : (
                      <Navigate to="/app" replace />
                    )
                  }
                />

                {/* Protected routes */}
                <Route
                  path="/app"
                  element={
                    <ProtectedRoute>
                      <UploadPage />
                    </ProtectedRoute>
                  }
                />
                <Route
                  path="/courses"
                  element={
                    <ProtectedRoute>
                      <CoursesPage />
                    </ProtectedRoute>
                  }
                />
                <Route
                  path="/usage"
                  element={
                    <ProtectedRoute>
                      <UsagePage />
                    </ProtectedRoute>
                  }
                />
                <Route
                  path="/process/:taskId"
                  element={
                    <ProtectedRoute>
                      <ProcessingPage />
                    </ProtectedRoute>
                  }
                />

                {/* Public demo or protected user workspace */}
                <Route path="/workspace" element={<Navigate to="/app" replace />} />
                <Route path="/workspace/:lectureId" element={<WorkspaceRouteWrapper />} />

                <Route path="/share/:slug" element={<ShareRedirect />} />
                <Route path="/print" element={<PrintPage />} />
                <Route path="*" element={<Navigate to="/" replace />} />
              </Routes>
            </Suspense>
          </MotionProvider>
        </Suspense>
      </BrowserRouter>
    </AppErrorBoundary>
  )
}