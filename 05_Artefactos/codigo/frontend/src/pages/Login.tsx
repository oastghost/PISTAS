import { useState, type FormEvent } from 'react'
import { Navigate } from 'react-router-dom'
import { useAuth } from '../auth'
import { errorMessage } from '../hooks'
import { homePath } from '../routes'

export function Login() {
  const { user, ready, login } = useAuth()
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  if (ready && user) return <Navigate to={homePath(user.role)} replace />

  async function onSubmit(e: FormEvent) {
    e.preventDefault()
    setBusy(true)
    setError(null)
    try {
      await login(username, password)
    } catch (err) {
      setError(errorMessage(err))
    } finally {
      setBusy(false)
    }
  }

  return (
    <>
      <header className="appbar">
        <span className="brand">A PISTAS</span>
        <span className="where">Gestão de stands, Aeroporto de Lisboa (LPPT)</span>
      </header>
      <main className="signin">
        <h1>Iniciar sessão</h1>
        <p className="muted">Plataforma Inteligente de Stands Tolerante a Avarias do Sudeis</p>

        <form className="panel" onSubmit={onSubmit}>
          <div className="panel-body form">
            <label className="field">
              Utilizador
              <input
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                autoComplete="username"
                required
                autoFocus
              />
            </label>
            <label className="field">
              Palavra-passe
              <input
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                autoComplete="current-password"
                required
              />
            </label>
            {error && (
              <p className="msg error" role="alert">
                {error}
              </p>
            )}
            <div className="form-actions">
              <button className="primary" disabled={busy}>
                {busy ? 'A entrar…' : 'Entrar'}
              </button>
            </div>
          </div>
        </form>

        {import.meta.env.VITE_USE_MOCK === 'true' && (
          <p className="demo">
            Dados simulados. Contas <code>tap</code>, <code>easyjet</code>, <code>ana</code>, <code>atc</code>,{' '}
            <code>menzies</code> e <code>portway</code>, palavra-passe <code>demo</code>.
          </p>
        )}
      </main>
    </>
  )
}
