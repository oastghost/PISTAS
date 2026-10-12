import { useState } from 'react'
import { api } from '../api'
import { ReservationTable } from '../components/ReservationTable'
import { Timeline } from '../components/Timeline'
import { formatDateTime } from '../format'
import { errorMessage, useLoad, usePlan } from '../hooks'

export function Ana() {
  const plan = usePlan()
  const reports = useLoad(() => api.listReports())
  const [error, setError] = useState<string | null>(null)
  const [removing, setRemoving] = useState<string | null>(null)

  async function remove(id: string, label: string) {
    if (!window.confirm(`Remover a alocação do voo ${label}? O despachante será avisado.`)) return
    setRemoving(id)
    setError(null)
    try {
      await api.removeReservation(id)
      plan.reload()
    } catch (err) {
      setError(errorMessage(err))
    } finally {
      setRemoving(null)
    }
  }

  const flightOf = (reservationId: string) =>
    plan.data?.reservations.find((r) => r.id === reservationId)?.flightNumber ?? reservationId

  return (
    <div className="stack">
      <h1>Revisão do plano</h1>
      <p className="muted">
        A ANA pode remover alocações. Não pode reorganizá-las. Quando remove, o despachante recebe um aviso com o
        contacto da ANA.
      </p>

      {error && <p className="alert error" role="alert">{error}</p>}
      {plan.error && <p className="alert error">{plan.error}</p>}

      {plan.data && (
        <>
          <Timeline stands={plan.data.stands} aircraft={plan.data.aircraft} reservations={plan.data.reservations} />
          <section className="card">
            <h2>Alocações</h2>
            <ReservationTable
              reservations={plan.data.reservations}
              stands={plan.data.stands}
              aircraft={plan.data.aircraft}
              empty="Não há alocações."
              action={(r) => (
                <button className="danger" disabled={removing === r.id} onClick={() => void remove(r.id, r.flightNumber)}>
                  Remover
                </button>
              )}
            />
          </section>
        </>
      )}

      <section className="card">
        <h2>Reportes do controlador</h2>
        {(reports.data ?? []).length === 0 ? (
          <p className="muted">Sem reportes.</p>
        ) : (
          <ul className="plain">
            {reports.data!.map((r) => (
              <li key={r.id}>
                <strong>{flightOf(r.reservationId)}</strong> · {formatDateTime(r.createdAt)} · {r.author}
                <br />
                {r.text}
              </li>
            ))}
          </ul>
        )}
      </section>
    </div>
  )
}
