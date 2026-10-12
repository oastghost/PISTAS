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
    <>
      <div className="page-head">
        <h1>Revisão do plano</h1>
        <p>
          A ANA pode remover alocações, não pode reorganizá-las. O despachante recebe um aviso com o contacto da ANA.
        </p>
      </div>

      <div className="stack">
        {error && (
          <p className="msg error" role="alert">
            {error}
          </p>
        )}
        {plan.error && (
          <p className="msg error" role="alert">
            {plan.error}
          </p>
        )}

        {plan.data && (
          <>
            <Timeline stands={plan.data.stands} aircraft={plan.data.aircraft} reservations={plan.data.reservations} />
            <ReservationTable
              title="Alocações"
              reservations={plan.data.reservations}
              stands={plan.data.stands}
              aircraft={plan.data.aircraft}
              empty="Não há alocações."
              action={(r) => (
                <button
                  type="button"
                  className="danger small"
                  disabled={removing === r.id}
                  onClick={() => void remove(r.id, r.flightNumber)}
                >
                  Remover
                </button>
              )}
            />
          </>
        )}

        <section className="panel">
          <div className="panel-head">
            <h2>Reportes do controlador</h2>
          </div>
          {(reports.data ?? []).length === 0 ? (
            <p className="empty">Sem reportes.</p>
          ) : (
            <div className="table-scroll">
              <table className="data">
                <thead>
                  <tr>
                    <th>Voo</th>
                    <th>Data</th>
                    <th>Autor</th>
                    <th>Descrição</th>
                  </tr>
                </thead>
                <tbody>
                  {reports.data!.map((r) => (
                    <tr key={r.id}>
                      <td className="num">{flightOf(r.reservationId)}</td>
                      <td className="num">{formatDateTime(r.createdAt)}</td>
                      <td>{r.author}</td>
                      <td>{r.text}</td>
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
