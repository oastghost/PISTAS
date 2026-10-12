import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom'
import { AuthProvider, useAuth } from './auth'
import { RoleLayout } from './components/Layout'
import { Ana } from './pages/Ana'
import { Controlador } from './pages/Controlador'
import { Despachante } from './pages/Despachante'
import { Handler } from './pages/Handler'
import { Login } from './pages/Login'
import { homePath } from './routes'

function Index() {
  const { user, ready } = useAuth()
  if (!ready) return null
  return <Navigate to={user ? homePath(user.role) : '/login'} replace />
}

export default function App() {
  return (
    <AuthProvider>
      <BrowserRouter>
        <Routes>
          <Route path="/login" element={<Login />} />
          <Route element={<RoleLayout role="despachante" />}>
            <Route path="/despachante" element={<Despachante />} />
          </Route>
          <Route element={<RoleLayout role="ana" />}>
            <Route path="/ana" element={<Ana />} />
          </Route>
          <Route element={<RoleLayout role="controlador" />}>
            <Route path="/controlador" element={<Controlador />} />
          </Route>
          <Route element={<RoleLayout role="handler" />}>
            <Route path="/handler" element={<Handler />} />
          </Route>
          <Route path="*" element={<Index />} />
        </Routes>
      </BrowserRouter>
    </AuthProvider>
  )
}
