import { useState, type FormEvent } from 'react'
import { api } from '../api'
import { useAuth } from '../auth'
import { formatDateTime, ROLE_LABEL } from '../format'
import { errorMessage, useLoad } from '../hooks'
import type { ManagedAccount } from '../types'

const ACTION_LABEL: Record<string, string> = {
  airline_created: 'Companhia criada',
  user_created: 'Conta criada',
  user_disabled: 'Conta desativada',
  user_enabled: 'Conta reativada',
  password_reset: 'Palavra-passe redefinida',
  password_changed: 'Palavra-passe mudada pelo próprio',
  prefix_added: 'Prefixo acrescentado',
  prefix_removed: 'Prefixo removido',
  ana_removal: 'Alocação removida',
  login: 'Início de sessão',
  login_failed: 'Início de sessão falhado',
}

const MANAGED: ManagedAccount['role'][] = ['despachante', 'ana']

export function Contas() {
  const { user } = useAuth()
  const airlines = useLoad(() => api.listAirlines())
  const accounts = useLoad(() => api.listAccounts())
  const audit = useLoad(() => api.listAudit())
  const [error, setError] = useState<string | null>(null)
  const [ok, setOk] = useState<string | null>(null)

  const [airlineName, setAirlineName] = useState('')
  const [airlinePrefixes, setAirlinePrefixes] = useState('')
  const [newPrefix, setNewPrefix] = useState<{ airline: string; value: string } | null>(null)

  const [role, setRole] = useState<'despachante' | 'ana'>('despachante')
  const [company, setCompany] = useState('')
  const [name, setName] = useState('')
  const [username, setUsername] = useState('')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')

  const [resetId, setResetId] = useState<string | null>(null)
  const [resetPassword, setResetPassword] = useState('')
  const [busy, setBusy] = useState(false)

  function refresh() {
    airlines.reload()
    accounts.reload()
    audit.reload()
  }

  async function run(action: () => Promise<unknown>, done: string) {
    setBusy(true)
    setError(null)
    setOk(null)
    try {
      await action()
      setOk(done)
      refresh()
      return true
    } catch (err) {
      setError(errorMessage(err))
      return false
    } finally {
      setBusy(false)
    }
  }

  async function addAirline(e: FormEvent) {
    e.preventDefault()
    const prefixes = airlinePrefixes.split(/[\s,;]+/).filter(Boolean)
    if (await run(() => api.createAirline(airlineName, prefixes), `Companhia ${airlineName.trim()} criada com o prefixo ${prefixes.join(', ').toUpperCase()}.`)) {
      setAirlineName('')
      setAirlinePrefixes('')
    }
  }

  async function addAccount(e: FormEvent) {
    e.preventDefault()
    const created = await run(
      () => api.createAccount({ username, name, email, role, company: role === 'despachante' ? company : null, password }),
      `Conta ${username} criada. Entregue a palavra-passe temporária por um canal seguro: será obrigatório mudá-la no primeiro início de sessão.`,
    )
    if (created) {
      setName('')
      setUsername('')
      setEmail('')
      setPassword('')
    }
  }

  async function addPrefix(e: FormEvent) {
    e.preventDefault()
    if (!newPrefix) return
    if (await run(() => api.addAirlinePrefix(newPrefix.airline, newPrefix.value), `Prefixo ${newPrefix.value.toUpperCase()} acrescentado a ${newPrefix.airline}.`)) setNewPrefix(null)
  }

  async function removePrefix(airline: string, prefix: string) {
    if (!window.confirm(`Remover o prefixo ${prefix} de ${airline}? Os pedidos novos com esse prefixo deixam de ser aceites.`)) return
    await run(() => api.removeAirlinePrefix(airline, prefix), `Prefixo ${prefix} removido de ${airline}.`)
  }

  async function toggle(a: ManagedAccount) {
    const verb = a.active ? 'Desativar' : 'Reativar'
    if (a.active && !window.confirm(`${verb} a conta ${a.username}? Perde o acesso imediatamente.`)) return
    await run(() => api.updateAccount(a.id, { active: !a.active }), `Conta ${a.username} ${a.active ? 'desativada' : 'reativada'}.`)
  }

  async function reset(a: ManagedAccount, e: FormEvent) {
    e.preventDefault()
    if (await run(() => api.updateAccount(a.id, { password: resetPassword }), `Palavra-passe de ${a.username} redefinida. Terá de a mudar no próximo início de sessão.`)) {
      setResetId(null)
      setResetPassword('')
    }
  }

  const airlineNames = (airlines.data ?? []).map((a) => a.name)
  const needsCompany = role === 'despachante'

  return (
    <>
      <div className="page-head">
        <h1>Contas</h1>
        <p>
          Cada despachante pertence a uma companhia e vê os avisos dessa companhia. Só a supervisão cria contas, desativa
          acessos e redefine palavras-passe. Tudo fica no registo de alterações.
        </p>
      </div>

      <div className="stack">
        {error && (
          <p className="msg error" role="alert">
            {error}
          </p>
        )}
        {ok && (
          <p className="msg ok" role="status">
            {ok}
          </p>
        )}

        <div className="split">
          <section className="panel">
            <div className="panel-head">
              <h2>Companhias</h2>
            </div>
            <table className="data">
              <thead>
                <tr>
                  <th>Companhia</th>
                  <th>Prefixos de voo</th>
                  <th>Despachantes ativos</th>
                </tr>
              </thead>
              <tbody>
                {(airlines.data ?? []).map((a) => (
                  <tr key={a.name}>
                    <td>{a.name}</td>
                    <td>
                      {a.prefixes.length === 0 && <span className="muted">Nenhum. </span>}
                      {a.prefixes.map((p) => (
                        <span key={p} className="chip">
                          {p}
                          {a.prefixes.length > 1 && (
                            <button type="button" className="chip-x" aria-label={`Remover ${p} de ${a.name}`} onClick={() => void removePrefix(a.name, p)}>
                              ×
                            </button>
                          )}
                        </span>
                      ))}
                      {newPrefix?.airline === a.name ? (
                        <form className="inline-form" onSubmit={(e) => void addPrefix(e)}>
                          <input
                            value={newPrefix.value}
                            onChange={(e) => setNewPrefix({ airline: a.name, value: e.target.value })}
                            aria-label={`Novo prefixo de ${a.name}`}
                            maxLength={3}
                            size={4}
                            required
                          />
                          <button className="primary small" disabled={busy}>
                            Guardar
                          </button>
                          <button type="button" className="small" onClick={() => setNewPrefix(null)}>
                            Cancelar
                          </button>
                        </form>
                      ) : (
                        <button type="button" className="small" onClick={() => setNewPrefix({ airline: a.name, value: '' })}>
                          + Prefixo
                        </button>
                      )}
                    </td>
                    <td className="num">
                      {a.activeDispatchers} de {a.dispatchers}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
            <form className="panel-body form" onSubmit={addAirline}>
              <label className="field">
                Nova companhia
                <input value={airlineName} onChange={(e) => setAirlineName(e.target.value)} minLength={2} maxLength={40} required />
              </label>
              <label className="field">
                Prefixos de voo (separados por vírgula, por exemplo RYR, FR)
                <input
                  value={airlinePrefixes}
                  onChange={(e) => setAirlinePrefixes(e.target.value)}
                  placeholder="RYR, FR"
                  pattern="([A-Za-z0-9]{2,3}[\s,;]*)+"
                  title="Um ou mais prefixos de 2 ou 3 letras ou algarismos"
                  required
                />
              </label>
              <div className="form-actions">
                <button className="primary" disabled={busy}>
                  Criar companhia
                </button>
              </div>
            </form>
          </section>

          <form className="panel" onSubmit={addAccount}>
            <div className="panel-head">
              <h2>Nova conta</h2>
            </div>
            <div className="panel-body form">
              <label className="field">
                Tipo
                <select value={role} onChange={(e) => setRole(e.target.value as 'despachante' | 'ana')}>
                  <option value="despachante">Despachante de uma companhia</option>
                  <option value="ana">Operador da ANA</option>
                </select>
              </label>
              {needsCompany && (
                <label className="field">
                  Companhia
                  <select value={company} onChange={(e) => setCompany(e.target.value)} required>
                    <option value="">Escolher…</option>
                    {airlineNames.map((n) => (
                      <option key={n}>{n}</option>
                    ))}
                  </select>
                </label>
              )}
              <div className="form-row">
                <label className="field">
                  Nome
                  <input value={name} onChange={(e) => setName(e.target.value)} minLength={2} maxLength={80} required />
                </label>
                <label className="field">
                  Utilizador
                  <input
                    value={username}
                    onChange={(e) => setUsername(e.target.value)}
                    pattern="[A-Za-z0-9._\-]{3,40}"
                    title="3 a 40 letras, números, ponto, hífen ou sublinhado"
                    autoComplete="off"
                    required
                  />
                </label>
              </div>
              <label className="field">
                E-mail
                <input type="email" value={email} onChange={(e) => setEmail(e.target.value)} maxLength={120} required />
              </label>
              <label className="field">
                Palavra-passe temporária (mínimo 12 caracteres)
                <input
                  type="password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  minLength={12}
                  autoComplete="new-password"
                  required
                />
              </label>
              <div className="form-actions">
                <button className="primary" disabled={busy}>
                  Criar conta
                </button>
              </div>
            </div>
          </form>
        </div>

        <section className="panel">
          <div className="panel-head">
            <h2>Utilizadores</h2>
          </div>
          <div className="table-scroll">
            <table className="data">
              <thead>
                <tr>
                  <th>Utilizador</th>
                  <th>Nome</th>
                  <th>Perfil</th>
                  <th>Companhia</th>
                  <th>E-mail</th>
                  <th>Estado</th>
                  <th />
                </tr>
              </thead>
              <tbody>
                {(accounts.data ?? []).map((a) => {
                  const canManage = MANAGED.includes(a.role) && a.id !== user?.id
                  return (
                    <tr key={a.id} className={a.active ? undefined : 'struck'}>
                      <td className="num keep">{a.username}</td>
                      <td>{a.name}</td>
                      <td>{ROLE_LABEL[a.role]}</td>
                      <td>{a.company ?? ''}</td>
                      <td>{a.email ?? ''}</td>
                      <td className="keep">
                        <span className={`status ${a.active ? 'approved' : 'removed'}`}>{a.active ? 'Ativa' : 'Desativada'}</span>
                      </td>
                      <td className="actions">
                        {canManage &&
                          (resetId === a.id ? (
                            <form className="inline-form" onSubmit={(e) => void reset(a, e)}>
                              <input
                                type="password"
                                value={resetPassword}
                                onChange={(e) => setResetPassword(e.target.value)}
                                placeholder="Nova palavra-passe"
                                aria-label={`Nova palavra-passe de ${a.username}`}
                                minLength={12}
                                autoComplete="new-password"
                                required
                              />
                              <button className="primary small" disabled={busy}>
                                Guardar
                              </button>
                              <button type="button" className="small" onClick={() => setResetId(null)}>
                                Cancelar
                              </button>
                            </form>
                          ) : (
                            <>
                              <button
                                type="button"
                                className="small"
                                onClick={() => {
                                  setResetId(a.id)
                                  setResetPassword('')
                                }}
                              >
                                Nova palavra-passe
                              </button>{' '}
                              <button type="button" className={a.active ? 'danger small' : 'small'} disabled={busy} onClick={() => void toggle(a)}>
                                {a.active ? 'Desativar' : 'Reativar'}
                              </button>
                            </>
                          ))}
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        </section>

        <section className="panel">
          <div className="panel-head">
            <h2>Registo de alterações</h2>
          </div>
          {(audit.data ?? []).length === 0 ? (
            <p className="empty">Sem registos.</p>
          ) : (
            <div className="table-scroll">
              <table className="data">
                <thead>
                  <tr>
                    <th>Quando</th>
                    <th>Quem</th>
                    <th>O quê</th>
                    <th>Detalhe</th>
                  </tr>
                </thead>
                <tbody>
                  {audit.data!.map((e) => (
                    <tr key={e.id}>
                      <td className="num">{formatDateTime(e.at)}</td>
                      <td>{e.username ?? ''}</td>
                      <td>{ACTION_LABEL[e.action] ?? e.action}</td>
                      <td>{e.detail ?? ''}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </section>
      </div>
    </>
  )
}
