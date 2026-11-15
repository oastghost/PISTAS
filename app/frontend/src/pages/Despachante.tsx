import { useRef, useState, type FormEvent } from 'react'
import { api, ApiError } from '../api'
import { DateTimeField } from '../components/DateTimeField'
import { ReservationTable } from '../components/ReservationTable'
import { Timeline } from '../components/Timeline'
import { useAuth } from '../auth'
import { COMMON_ORIGINS, HOUR_MS, formatDateTime, formatTime, isIcao, isRegistration, matchesPrefix } from '../format'
import { errorMessage, useLoad, usePlan } from '../hooks'
import type { Reservation, Stand } from '../types'

/** The next full hour, so the form never opens in the past. */
function nextHour(): number {
  return Math.ceil(Date.now() / HOUR_MS) * HOUR_MS
}

const DURATIONS = [1, 2, 3, 4]

export function Despachante() {
  const { user } = useAuth()
  const plan = usePlan()
  const handlers = useLoad(() => api.listHandlers())
  const notices = useLoad(() => api.listNotices())

  const [registration, setRegistration] = useState('')
  async function dismiss(id?: string) {
    try {
      if (id) await api.dismissNotice(id)
      else await api.dismissAllNotices()
    } finally {
      notices.reload()
    }
  }

  const [flightNumber, setFlightNumber] = useState('')
  const [origin, setOrigin] = useState('')
  const [aircraftType, setAircraftType] = useState('A320')
  const [standId, setStandId] = useState('')
  const [start, setStart] = useState(nextHour)
  const [end, setEnd] = useState(() => nextHour() + HOUR_MS)
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

  const prefixes = user?.flightPrefixes ?? []

  // Choosing the arrival moves the departure with it, so the stay keeps its length (1 h at first).
  function changeStart(next: number) {
    const stay = end > start ? end - start : HOUR_MS
    touch(setStart)(next)
    setEnd(next + stay)
  }

  async function bid(forStandId: string) {
    if (!isRegistration(registration)) {
      setError('A matrícula não é válida. Exemplos: CS-TNP, D-AIUA, N123AB.')
      setAlternatives(null)
      setResult(null)
      return
    }
    if (!isIcao(origin)) {
      setError('A origem tem de ser um código ICAO de 4 letras, por exemplo LEMD ou EGLL.')
      setAlternatives(null)
      setResult(null)
      return
    }
    if (end <= start) {
      setError('A saída tem de ser depois da chegada.')
      setAlternatives(null)
      setResult(null)
      return
    }
    if (prefixes.length > 0 && !matchesPrefix(flightNumber, prefixes)) {
      setError(`O número de voo tem de começar por ${prefixes.join(' ou ')} seguido de 1 a 4 algarismos (por exemplo ${prefixes[0]}1234).`)
      setAlternatives(null)
      setResult(null)
      return
    }
    setBusy(true)
    setError(null)
    setAlternatives(null)
    setResult(null)
    const request = {
      requestId: requestId.current,
      standId: forStandId,
      registration: registration.trim().toUpperCase(),
      flightNumber,
      origin: origin.trim().toUpperCase(),
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
            {notices.data!.length > 1 && (
              <button type="button" className="small" onClick={() => void dismiss()}>
                Dispensar todos
              </button>
            )}
          </div>
          <ul className="notice-list">
            {notices.data!.map((n) => (
              <li key={n.id} className="notice-item">
                <span>
                  <time>{formatDateTime(n.createdAt)}</time>
                  {n.message}
                </span>
                <button type="button" className="small" onClick={() => void dismiss(n.id)}>
                  Dispensar
                </button>
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
              Matrícula da aeronave
              <input
                value={registration}
                onChange={(e) => touch(setRegistration)(e.target.value.toUpperCase())}
                placeholder="CS-TNP"
                required
                maxLength={8}
                autoComplete="off"
                spellCheck={false}
              />
            </label>

            <div className="form-row">
              <label className="field">
                Voo de chegada
                <input
                  value={flightNumber}
                  onChange={(e) => touch(setFlightNumber)(e.target.value.toUpperCase())}
                  placeholder={`${prefixes[0] ?? 'TP'}1234`}
                  required
                  maxLength={10}
                  autoComplete="off"
                />
              </label>
              <label className="field">
                Origem (ICAO)
                <input
                  value={origin}
                  onChange={(e) => touch(setOrigin)(e.target.value.toUpperCase().replace(/[^A-Z]/g, ''))}
                  placeholder="LEMD"
                  list="icao-origins"
                  required
                  maxLength={4}
                  autoComplete="off"
                  spellCheck={false}
                />
                <datalist id="icao-origins">
                  {COMMON_ORIGINS.map(([code, name]) => (
                    <option key={code} value={code}>
                      {name}
                    </option>
                  ))}
                </datalist>
              </label>
            </div>
            <span className="hint-line">
              {prefixes.length > 0
                ? `O voo de chegada começa por ${prefixes.join(' ou ')}, seguido de 1 a 4 algarismos. A aeronave é identificada pela matrícula.`
                : 'A sua companhia ainda não tem prefixo de voo. Peça à supervisão da ANA.'}
            </span>

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

            <DateTimeField label="Chegada ao stand" value={start} onChange={changeStart} />
            <DateTimeField
              label="Saída do stand"
              value={end}
              minDay={start}
              onChange={(v) => touch(setEnd)(v)}
            />
            <div className="dtf-quick" role="group" aria-label="Duração da permanência">
              <span className="muted">Permanência</span>
              {DURATIONS.map((h) => (
                <button
                  key={h}
                  type="button"
                  className="chip"
                  aria-pressed={end - start === h * HOUR_MS}
                  onClick={() => touch(setEnd)(start + h * HOUR_MS)}
                >
                  {h} h
                </button>
              ))}
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
                <strong>Pedido aprovado.</strong> {result.registration} no {standName(result.standId)}, das{' '}
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
            showRequester
            empty="Ainda não fez nenhum pedido."
          />
        </div>
      </div>
    </>
  )
}
