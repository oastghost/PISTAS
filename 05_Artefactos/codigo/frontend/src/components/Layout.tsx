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

  if (!ready) return <p className="empty">A carregar…</p>
  if (!user) return <Navigate to="/login" replace />
  if (user.role !== role) return <Navigate to={homePath(user.role)} replace />

  return (
    <>
      <header className="appbar">
        <span className="brand">A PISTAS</span>
        <span className="where">Gestão de stands, Aeroporto de Lisboa (LPPT)</span>
        <span className="who">
          {user.name}
          <small>{user.company ? `${ROLE_LABEL[user.role]}, ${user.company}` : ROLE_LABEL[user.role]}</small>
        </span>
        <button type="button" onClick={() => void logout()}>
          Terminar sessão
        </button>
      </header>
      <main className="page">
        <Outlet />
      </main>
    </>
  )
}
