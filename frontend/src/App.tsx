import { BrowserRouter, Routes, Route } from 'react-router-dom'
import { Workspace } from './components/layout/Workspace'
import { PrintPage } from './components/PrintPage'
import { ToastContainer } from './components/ui/ToastContainer'
export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<><Workspace /><ToastContainer /></>} />
        <Route path="/print" element={<PrintPage />} />
      </Routes>
    </BrowserRouter>
  )
}