import { useState, type FormEvent } from 'react'
import { useAuth } from '../auth'
import { errorMessage } from '../hooks'

/**
 * Shown instead of the app while the account still has the temporary password. The backend
 * refuses every other request until this succeeds, so this is not just a screen flow.
 */
export function ChangePassword() {
  const { user, logout, changePassword } = useAuth()
  const [current, setCurrent] = useState('')
  const [next, setNext] = useState('')
  const [again, setAgain] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  async function onSubmit(e: FormEvent) {
    e.preventDefault()
    if (next !== again) {
      setError('As duas palavras-passe novas não coincidem.')
      return
    }
    setBusy(true)
    setError(null)
    try {
      await changePassword(current, next)
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
        <span className="who">{user?.name}</span>
        <button type="button" onClick={() => void logout()}>
          Terminar sessão
        </button>
      </header>
      <main className="signin">
        <h1>Defina a sua palavra-passe</h1>
        <p className="muted">
          A palavra-passe que recebeu é temporária e outra pessoa a conhece. Escolha uma só sua para continuar.
        </p>
        <form className="panel" onSubmit={onSubmit}>
          <div className="panel-body form">
            <label className="field">
              Palavra-passe temporária
              <input
                type="password"
                value={current}
                onChange={(e) => setCurrent(e.target.value)}
                autoComplete="current-password"
                required
              />
            </label>
            <label className="field">
              Palavra-passe nova (mínimo 12 caracteres)
              <input
                type="password"
                value={next}
                onChange={(e) => setNext(e.target.value)}
                minLength={12}
                autoComplete="new-password"
                required
              />
            </label>
            <label className="field">
              Repita a palavra-passe nova
              <input
                type="password"
                value={again}
                onChange={(e) => setAgain(e.target.value)}
                minLength={12}
                autoComplete="new-password"
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
                Guardar e continuar
              </button>
            </div>
          </div>
        </form>
      </main>
    </>
  )
}
