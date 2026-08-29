import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { AuthProvider, useAuth } from './context/AuthContext'
import { CrossGraphProvider } from './context/CrossGraphContext'
import Layout from './components/Layout'
import LoginPage from './pages/LoginPage'
import DashboardPage from './pages/DashboardPage'
import CasesPage from './pages/CasesPage'
import CaseDetailPage from './pages/CaseDetailPage'
import NetworkExplorerPage from './pages/NetworkExplorerPage'
import EntitiesPage from './pages/EntitiesPage'
import EntityProfilePage from './pages/EntityProfilePage'
import AlertsPage from './pages/AlertsPage'
import IngestionPage from './pages/IngestionPage'
import AdminPage from './pages/AdminPage'
import ReportsPage from './pages/ReportsPage'
import ThreatScorePage from './pages/ThreatScorePage'
import PatternsPage from './pages/PatternsPage'
import IntelligencePage from './pages/IntelligencePage'
import SerialPatternsPage from './pages/SerialPatternsPage'

function ProtectedRoute({ children }: { children: React.ReactNode }) {
  const { user, loading } = useAuth()
  if (loading) return (
    <div className="flex items-center justify-center h-screen" style={{ background: 'var(--ops-bg-void)' }}>
      <div className="loading-spinner" />
    </div>
  )
  if (!user) return <Navigate to="/login" />
  return <>{children}</>
}

function App() {
  return (
    <AuthProvider>
      <CrossGraphProvider>
      <BrowserRouter>
        <Routes>
          <Route path="/login" element={<LoginPage />} />
          <Route path="/" element={<ProtectedRoute><Layout /></ProtectedRoute>}>
            <Route index element={<DashboardPage />} />
            <Route path="cases" element={<CasesPage />} />
            <Route path="cases/:caseId" element={<CaseDetailPage />} />
            <Route path="cases/:caseId/network" element={<NetworkExplorerPage />} />
            <Route path="people-network" element={<NetworkExplorerPage />} />
            <Route path="cases/:caseId/people-network" element={<NetworkExplorerPage />} />
            <Route path="cases/:caseId/entities" element={<EntitiesPage />} />
            <Route path="entities/:entityId" element={<EntityProfilePage />} />
            <Route path="cases/:caseId/alerts" element={<AlertsPage />} />
            <Route path="cases/:caseId/ingestion" element={<IngestionPage />} />
            <Route path="cases/:caseId/reports" element={<ReportsPage />} />
            <Route path="reports" element={<ReportsPage />} />
            <Route path="threat-scores" element={<ThreatScorePage />} />
            <Route path="patterns" element={<PatternsPage />} />
            <Route path="intelligence" element={<IntelligencePage />} />
            <Route path="serial-patterns" element={<SerialPatternsPage />} />
            <Route path="admin" element={<AdminPage />} />
          </Route>
        </Routes>
      </BrowserRouter>
      </CrossGraphProvider>
    </AuthProvider>
  )
}

export default App
