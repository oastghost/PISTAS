import { Navigate, Outlet } from 'react-router-dom'
import { useAuth } from '../auth'
import { ROLE_LABEL } from '../format'
import { homePath } from '../routes'
import type { Role } from '../types'

/**
 * Frontend guard only, for a sensible screen flow. The backend enforces the roles.
 */
export function RoleLayout({ role }: { role: Role }) {
  const { user, ready, logout } = useAuth()

  if (!ready) return <p className="center muted">A carregar…</p>
  if (!user) return <Navigate to="/login" replace />
  if (user.role !== role) return <Navigate to={homePath(user.role)} replace />

  return (
    <>
      <header className="topbar">
        <strong>A PISTAS</strong>
        <span className="muted-light">
          {ROLE_LABEL[user.role]} · {user.name}
        </span>
        <button className="ghost" onClick={() => void logout()}>Terminar sessão</button>
      </header>
      <main className="page">
        <Outlet />
      </main>
    </>
  )
}
