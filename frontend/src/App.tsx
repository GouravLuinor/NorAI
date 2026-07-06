import { BrowserRouter, Routes, Route } from 'react-router-dom'
import { UploadPage } from './pages/UploadPage'
import { ProcessingPage } from './pages/ProcessingPage'
import { Workspace } from './components/layout/Workspace'
import { PrintPage } from './components/PrintPage'
import { ToastContainer } from './components/ui/ToastContainer'

export default function App() {
  return (
    <BrowserRouter>
      <ToastContainer />
      <Routes>
        <Route path="/" element={<UploadPage />} />
        <Route path="/process/:taskId" element={<ProcessingPage />} />
        <Route path="/workspace" element={<Workspace />} />
        <Route path="/print" element={<PrintPage />} />
        <Route path="/workspace/:lectureId" element={<Workspace />} />
      </Routes>
    </BrowserRouter>
  )
}