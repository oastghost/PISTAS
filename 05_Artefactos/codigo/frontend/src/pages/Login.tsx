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
    <main className="login">
      <form className="card login-card" onSubmit={onSubmit}>
        <h1>A PISTAS</h1>
        <p className="muted">Plataforma Inteligente de Stands Tolerante a Avarias do Sudeis</p>

        <label>
          Utilizador
          <input value={username} onChange={(e) => setUsername(e.target.value)} autoComplete="username" required autoFocus />
        </label>
        <label>
          Palavra-passe
          <input type="password" value={password} onChange={(e) => setPassword(e.target.value)} autoComplete="current-password" required />
        </label>

        {error && <p className="alert error" role="alert">{error}</p>}
        <button className="primary" disabled={busy}>{busy ? 'A entrar…' : 'Entrar'}</button>

        <details className="demo">
          <summary>Contas de demonstração (simuladas)</summary>
          <p>
            Palavra-passe <code>demo</code> para: <code>tap</code>, <code>easyjet</code> (despachantes),{' '}
            <code>ana</code>, <code>atc</code> (controlador), <code>menzies</code>, <code>portway</code> (ground handlers).
          </p>
        </details>
      </form>
    </main>
  )
}
