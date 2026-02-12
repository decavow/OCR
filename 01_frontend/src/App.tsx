import { BrowserRouter, Routes, Route } from 'react-router-dom'
import { AuthProvider } from './context/AuthContext'

// Pages
import LoginPage from './pages/LoginPage'
import RegisterPage from './pages/RegisterPage'
import DashboardPage from './pages/DashboardPage'
import BatchesPage from './pages/BatchesPage'
import BatchDetailPage from './pages/BatchDetailPage'
import ResultViewerPage from './pages/ResultViewerPage'
import UploadPage from './pages/UploadPage'
import SettingsPage from './pages/SettingsPage'
import NotFoundPage from './pages/NotFoundPage'
import AdminServicesPage from './pages/AdminServicesPage'
import AdminDashboardPage from './pages/AdminDashboardPage'
import AdminUsersPage from './pages/AdminUsersPage'
import AdminSystemHealthPage from './pages/AdminSystemHealthPage'

// Components
import ProtectedRoute from './components/auth/ProtectedRoute'
import AdminRoute from './components/auth/AdminRoute'
import MainLayout from './components/layout/MainLayout'

function App() {
  return (
    <AuthProvider>
      <BrowserRouter>
        <Routes>
          {/* Public routes */}
          <Route path="/login" element={<LoginPage />} />
          <Route path="/register" element={<RegisterPage />} />

          {/* Protected routes */}
          <Route element={<ProtectedRoute />}>
            <Route element={<MainLayout />}>
              <Route path="/" element={<DashboardPage />} />
              <Route path="/dashboard" element={<DashboardPage />} />
              <Route path="/batches" element={<BatchesPage />} />
              <Route path="/batches/:id" element={<BatchDetailPage />} />
              <Route path="/batches/:batchId/files/:fileId" element={<ResultViewerPage />} />
              <Route path="/upload" element={<UploadPage />} />
              <Route path="/settings" element={<SettingsPage />} />

              {/* Admin routes */}
              <Route element={<AdminRoute />}>
                <Route path="/admin/dashboard" element={<AdminDashboardPage />} />
                <Route path="/admin/services" element={<AdminServicesPage />} />
                <Route path="/admin/users" element={<AdminUsersPage />} />
                <Route path="/admin/system" element={<AdminSystemHealthPage />} />
              </Route>
            </Route>
          </Route>

          {/* 404 */}
          <Route path="*" element={<NotFoundPage />} />
        </Routes>
      </BrowserRouter>
    </AuthProvider>
  )
}

export default App
