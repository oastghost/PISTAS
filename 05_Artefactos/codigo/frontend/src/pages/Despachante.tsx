import { useRef, useState, type FormEvent } from 'react'
import { api, ApiError } from '../api'
import { ReservationTable } from '../components/ReservationTable'
import { Timeline } from '../components/Timeline'
import { useAuth } from '../auth'
import { formatDateTime, formatTime } from '../format'
import { errorMessage, useLoad, usePlan } from '../hooks'
import type { Reservation, Stand } from '../types'

function defaultLocal(hour: number): string {
  const d = new Date()
  d.setHours(hour, 0, 0, 0)
  const p = (n: number) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())}T${p(d.getHours())}:${p(d.getMinutes())}`
}

export function Despachante() {
  const { user } = useAuth()
  const plan = usePlan()
  const handlers = useLoad(() => api.listHandlers())
  const notices = useLoad(() => api.listNotices())

  const [flightNumber, setFlightNumber] = useState('')
  const [aircraftType, setAircraftType] = useState('A320')
  const [standId, setStandId] = useState('')
  const [start, setStart] = useState(() => defaultLocal(18))
  const [end, setEnd] = useState(() => defaultLocal(20))
  const [wantHandling, setWantHandling] = useState(false)
  const [handler, setHandler] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [alternatives, setAlternatives] = useState<Stand[] | null>(null)
  const [result, setResult] = useState<Reservation | null>(null)

  // New id per attempt. It only survives a retry of the exact same, unchanged form,
  // so a lost answer can be resent safely without creating a second reservation.
  const requestId = useRef(crypto.randomUUID())
  const touch = <T,>(setter: (v: T) => void) => (v: T) => {
    requestId.current = crypto.randomUUID()
    setter(v)
  }

  const aircraft = plan.data?.aircraft.find((a) => a.code === aircraftType)
  const stands = plan.data?.stands ?? []
  const fits = (s: Stand) => !aircraft || s.maxWingspanM >= aircraft.wingspanM
  const apronNames = [...new Set(stands.map((s) => s.apron))]
  const wanted = stands.find((s) => s.id === standId)

  async function bid(forStandId: string) {
    setBusy(true)
    setError(null)
    setAlternatives(null)
    setResult(null)
    const request = {
      requestId: requestId.current,
      standId: forStandId,
      flightNumber,
      aircraftType,
      start: new Date(start).toISOString(),
      end: new Date(end).toISOString(),
      handler: wantHandling && handler ? handler : null,
    }
    try {
      const reservation = await api.requestStand(request)
      setResult(reservation)
      requestId.current = crypto.randomUUID()
      plan.reload()
    } catch (err) {
      setError(errorMessage(err))
      if (err instanceof ApiError && (err.code === 'STAND_UNAVAILABLE' || err.code === 'STAND_TOO_SMALL')) {
        try {
          setAlternatives(await api.suggestStands(request))
        } catch {
          setAlternatives(null)
        }
      }
    } finally {
      setBusy(false)
    }
  }

  function onSubmit(e: FormEvent) {
    e.preventDefault()
    void bid(standId)
  }

  function takeAlternative(s: Stand) {
    requestId.current = crypto.randomUUID()
    setStandId(s.id)
    void bid(s.id)
  }

  const mine = (plan.data?.reservations ?? []).filter((r) => r.company === user?.company)
  const standName = (id: string) => stands.find((s) => s.id === id)?.name ?? id
  const tooSmall = wanted !== undefined && !fits(wanted)

  return (
    <>
      <div className="page-head">
        <h1>Pedido de stand</h1>
        <p>Escolha o stand pretendido. Se estiver livre e a aeronave couber, o pedido é aprovado de imediato.</p>
      </div>

      {(notices.data ?? []).length > 0 && (
        <section className="panel alert" aria-label="Avisos da ANA" style={{ marginBottom: 20 }}>
          <div className="panel-head">
            <h2>Avisos da ANA</h2>
          </div>
          <ul className="notice-list">
            {notices.data!.map((n) => (
              <li key={n.id}>
                <time>{formatDateTime(n.createdAt)}</time>
                {n.message}
              </li>
            ))}
          </ul>
        </section>
      )}

      <div className="split">
        <form className="panel" onSubmit={onSubmit}>
          <div className="panel-head">
            <h2>Novo pedido</h2>
          </div>
          <div className="panel-body form">
            <label className="field">
              Número do voo
              <input
                value={flightNumber}
                onChange={(e) => touch(setFlightNumber)(e.target.value)}
                placeholder="TP1234"
                required
                maxLength={10}
              />
            </label>

            <label className="field">
              Tipo de aeronave
              <select value={aircraftType} onChange={(e) => touch(setAircraftType)(e.target.value)}>
                {(plan.data?.aircraft ?? []).map((a) => (
                  <option key={a.code} value={a.code}>
                    {a.label}, categoria {a.category}
                  </option>
                ))}
              </select>
              {aircraft && (
                <span className="hint">
                  Envergadura {aircraft.wingspanM.toLocaleString('pt-PT')} m. {stands.filter(fits).length} de{' '}
                  {stands.length} stands aceitam esta aeronave.
                </span>
              )}
            </label>

            <label className="field">
              Stand pretendido
              <select value={standId} onChange={(e) => touch(setStandId)(e.target.value)} required>
                <option value="">Escolher stand</option>
                {apronNames.map((apron) => (
                  <optgroup key={apron} label={apron === 'Temporária' ? 'Apron temporário' : `Apron ${apron}`}>
                    {stands
                      .filter((s) => s.apron === apron)
                      .map((s) => (
                        <option key={s.id} value={s.id} disabled={!fits(s)}>
                          {s.name}, {s.critical}
                          {fits(s) ? '' : ' (não aceita esta aeronave)'}
                        </option>
                      ))}
                  </optgroup>
                ))}
              </select>
              <span className="hint">Também pode escolher o stand no plano, clicando no nome dele.</span>
            </label>

            <div className="form-row">
              <label className="field">
                Chegada ao stand
                <input
                  type="datetime-local"
                  value={start}
                  onChange={(e) => touch(setStart)(e.target.value)}
                  required
                />
              </label>
              <label className="field">
                Saída do stand
                <input type="datetime-local" value={end} onChange={(e) => touch(setEnd)(e.target.value)} required />
              </label>
            </div>

            <label className="check">
              <input
                type="checkbox"
                checked={wantHandling}
                onChange={(e) => touch(setWantHandling)(e.target.checked)}
              />
              Pedir assistência em terra
            </label>
            {wantHandling && (
              <label className="field">
                Empresa de assistência em terra
                <select value={handler} onChange={(e) => touch(setHandler)(e.target.value)} required>
                  <option value="">Escolher empresa</option>
                  {(handlers.data ?? []).map((h) => (
                    <option key={h} value={h}>
                      {h}
                    </option>
                  ))}
                </select>
              </label>
            )}

            {tooSmall && (
              <p className="msg error" role="alert">
                O {wanted.name} não aceita esta aeronave. Escolha outro stand ou outro tipo de aeronave.
              </p>
            )}
            {error && (
              <p className="msg error" role="alert">
                {error}
              </p>
            )}
            {alternatives && (
              <div role="status">
                {alternatives.length > 0 ? (
                  <>
                    <p className="muted">Stands livres neste período, do mais adequado para o menos adequado:</p>
                    <ul className="alt-list">
                      {alternatives.map((s) => (
                        <li key={s.id}>
                          <span>
                            {s.name}, Apron {s.apron}
                          </span>
                          <button type="button" className="small" disabled={busy} onClick={() => takeAlternative(s)}>
                            Pedir este stand
                          </button>
                        </li>
                      ))}
                    </ul>
                  </>
                ) : (
                  <p className="muted">Não há stands alternativos livres para este voo neste período.</p>
                )}
              </div>
            )}
            {result && (
              <p className="msg ok" role="status">
                <strong>Pedido aprovado.</strong> Voo {result.flightNumber} no {standName(result.standId)}, das{' '}
                {formatTime(result.start)} às {formatTime(result.end)}.
              </p>
            )}

            <div className="form-actions">
              <button className="primary" disabled={busy || plan.loading || !standId || tooSmall}>
                {busy ? 'A enviar…' : 'Pedir stand'}
              </button>
            </div>
          </div>
        </form>

        <div className="stack">
          {plan.error && (
            <p className="msg error" role="alert">
              {plan.error}
            </p>
          )}
          {plan.data && (
            <Timeline
              stands={plan.data.stands}
              aircraft={plan.data.aircraft}
              reservations={plan.data.reservations}
              highlightCompany={user?.company}
              pickedStandId={standId}
              canPick={fits}
              onPickStand={(s) => touch(setStandId)(s.id)}
            />
          )}
          <ReservationTable
            title="Os meus pedidos"
            reservations={mine}
            stands={stands}
            aircraft={plan.data?.aircraft ?? []}
            showCompany={false}
            empty="Ainda não fez nenhum pedido."
          />
        </div>
      </div>
    </>
  )
}
