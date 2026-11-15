import { useState, type FormEvent } from 'react'
import { api } from '../api'
import { ReservationTable } from '../components/ReservationTable'
import { Timeline } from '../components/Timeline'
import { errorMessage, usePlan } from '../hooks'
import type { Reservation } from '../types'

export function Controlador() {
  const plan = usePlan()
  const [selected, setSelected] = useState<Reservation | null>(null)
  const [text, setText] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [sent, setSent] = useState(false)

  async function onSubmit(e: FormEvent) {
    e.preventDefault()
    if (!selected) return
    setBusy(true)
    setError(null)
    setSent(false)
    try {
      await api.createReport(selected.id, text)
      setText('')
      setSent(true)
    } catch (err) {
      setError(errorMessage(err))
    } finally {
      setBusy(false)
    }
  }

  return (
    <>
      <div className="page-head">
        <h1>Plano em vigor</h1>
        <p>Vista só de leitura. Se a ANA não detetou um problema, escolha a aeronave no plano e reporte-o.</p>
      </div>

      {plan.error && (
        <p className="msg error" role="alert">
          {plan.error}
        </p>
      )}

      {plan.data && (
        <div className="split">
          <form className="panel" onSubmit={onSubmit}>
            <div className="panel-head">
              <h2>Reportar um problema</h2>
            </div>
            <div className="panel-body form">
              {selected ? (
                <p>
                  Aeronave <strong>{selected.registration}</strong>, {selected.company}
                </p>
              ) : (
                <p className="muted">Clique numa aeronave do plano para o selecionar.</p>
              )}
              <label className="field">
                Descrição
                <textarea value={text} onChange={(e) => setText(e.target.value)} rows={4} maxLength={500} required />
              </label>
              {error && (
                <p className="msg error" role="alert">
                  {error}
                </p>
              )}
              {sent && (
                <p className="msg ok" role="status">
                  <strong>Reporte enviado.</strong> A ANA vai receber a descrição.
                </p>
              )}
              <div className="form-actions">
                <button className="primary" disabled={!selected || busy}>
                  Enviar reporte
                </button>
              </div>
            </div>
          </form>

          <div className="stack">
            <Timeline
              stands={plan.data.stands}
              aircraft={plan.data.aircraft}
              reservations={plan.data.reservations}
              selectedId={selected?.id}
              onSelect={(r) => {
                setSelected(r)
                setSent(false)
              }}
            />
            <ReservationTable
              title="Alocações"
              reservations={plan.data.reservations}
              stands={plan.data.stands}
              aircraft={plan.data.aircraft}
              empty="Não há alocações."
            />
          </div>
        </div>
      )}
    </>
  )
}
