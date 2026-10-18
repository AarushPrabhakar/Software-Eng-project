import { Routes, Route, Navigate } from 'react-router-dom'
import { AuthProvider, useAuth } from './context/AuthContext.jsx'
import Nav from './components/Nav.jsx'
import Login from './pages/Login.jsx'
import Register from './pages/Register.jsx'
import Feed from './pages/Feed.jsx'
import ReportForm from './pages/ReportForm.jsx'
import ItemDetail from './pages/ItemDetail.jsx'
import ClaimDetail from './pages/ClaimDetail.jsx'
import MyActivity from './pages/MyActivity.jsx'
import Notifications from './pages/Notifications.jsx'
import Admin from './pages/Admin.jsx'
import Landing from './pages/Landing.jsx'

function ProtectedShell() {
  const { isAuthenticated, loading, user } = useAuth()

  if (loading) {
    return (
      <div className="shell">
        <div className="page" aria-busy="true" />
      </div>
    )
  }

  if (!isAuthenticated) {
    return <Navigate to="/" replace />
  }

  return (
    <div className="shell">
      <Nav user={user} />
      <Routes>
        <Route path="/feed" element={<Feed />} />
        <Route path="/report/lost" element={<ReportForm type="lost" />} />
        <Route path="/report/found" element={<ReportForm type="found" />} />
        <Route path="/item/:id" element={<ItemDetail />} />
        <Route path="/claim/:id" element={<ClaimDetail />} />
        <Route path="/my" element={<MyActivity />} />
        <Route path="/notifications" element={<Notifications />} />
        <Route path="/admin" element={<Admin />} />
        <Route path="*" element={<Navigate to="/feed" replace />} />
      </Routes>
    </div>
  )
}

function AppRoutes() {
  const { isAuthenticated, loading } = useAuth()

  return (
    <Routes>
      <Route
        path="/login"
        element={!loading && isAuthenticated ? <Navigate to="/feed" replace /> : <Login />}
      />
      <Route
        path="/register"
        element={!loading && isAuthenticated ? <Navigate to="/feed" replace /> : <Register />}
      />
      <Route
        path="/"
        element={!loading && isAuthenticated ? <Navigate to="/feed" replace /> : loading ? null : <Landing />}
      />
      <Route path="/*" element={<ProtectedShell />} />
    </Routes>
  )
}

export default function App() {
  return (
    <AuthProvider>
      <AppRoutes />
    </AuthProvider>
  )
}
