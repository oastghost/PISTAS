import { NavLink, Navigate, Outlet } from 'react-router-dom'
import { useAuth } from '../auth'
import { ROLE_LABEL } from '../format'
import { ChangePassword } from '../pages/ChangePassword'
import { homePath } from '../routes'
import type { Role } from '../types'

/**
 * Frontend guard only, for a sensible screen flow. The backend enforces the roles.
 */
export function RoleLayout({ role }: { role: Role | Role[] }) {
  const { user, ready, logout } = useAuth()

  if (!ready) return <p className="empty">A carregar…</p>
  if (!user) return <Navigate to="/login" replace />
  if (!(Array.isArray(role) ? role : [role]).includes(user.role)) return <Navigate to={homePath(user.role)} replace />

  if (user.mustChangePassword) return <ChangePassword />

  return (
    <>
      <header className="appbar">
        <span className="brand">
          <img src="/PISTAS_logo.png" alt="A PISTAS" width="40" height="40" />
        </span>
        <span className="where">Gestão de stands, Aeroporto de Lisboa (LPPT)</span>
        {user.role === 'ana_supervisor' && (
          <nav aria-label="Secções">
            <NavLink to="/ana">Plano</NavLink>
            <NavLink to="/contas">Contas</NavLink>
          </nav>
        )}
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
