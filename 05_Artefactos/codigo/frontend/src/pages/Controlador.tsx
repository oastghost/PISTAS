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
    <div className="stack">
      <h1>Plano em vigor</h1>
      <p className="muted">
        Vista só de leitura. Se a ANA não detetou um problema, escolha o voo no plano e use “Reportar”.
      </p>
      {plan.error && <p className="alert error">{plan.error}</p>}

      {plan.data && (
        <>
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

          <form className="card" onSubmit={onSubmit}>
            <h2>Reportar problema</h2>
            {selected ? (
              <p>
                Voo selecionado: <strong>{selected.flightNumber}</strong> ({selected.company})
              </p>
            ) : (
              <p className="muted">Clique num voo do plano para o selecionar.</p>
            )}
            <label>
              Descrição
              <textarea value={text} onChange={(e) => setText(e.target.value)} rows={3} maxLength={500} required />
            </label>
            {error && <p className="alert error" role="alert">{error}</p>}
            {sent && <p className="alert ok" role="status">Reporte enviado à ANA.</p>}
            <button className="primary" disabled={!selected || busy}>Reportar</button>
          </form>

          <section className="card">
            <h2>Alocações</h2>
            <ReservationTable
              reservations={plan.data.reservations}
              stands={plan.data.stands}
              aircraft={plan.data.aircraft}
              empty="Não há alocações."
            />
          </section>
        </>
      )}
    </div>
  )
}
