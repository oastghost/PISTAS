import type { ReactNode } from 'react'
import { formatRange } from '../format'
import type { AircraftType, Reservation, Stand } from '../types'

interface Props {
  title: string
  reservations: Reservation[]
  stands: Stand[]
  aircraft: AircraftType[]
  empty: string
  /** Extra last column, for example a remove button. */
  action?: (reservation: Reservation) => ReactNode
  showCompany?: boolean
}

export function ReservationTable({
  title,
  reservations,
  stands,
  aircraft,
  empty,
  action,
  showCompany = true,
}: Props) {
  const standLabel = (id: string) => {
    const s = stands.find((x) => x.id === id)
    return s ? `${s.name} (${s.category})` : id
  }
  const aircraftLabel = (code: string) => {
    const a = aircraft.find((x) => x.code === code)
    return a ? `${a.label} (${a.category})` : code
  }
  const sorted = [...reservations].sort((a, b) => Date.parse(a.start) - Date.parse(b.start))

  return (
    <section className="panel">
      <div className="panel-head">
        <h2>{title}</h2>
        <span className="muted">{reservations.length === 1 ? '1 voo' : `${reservations.length} voos`}</span>
      </div>
      {sorted.length === 0 ? (
        <p className="empty">{empty}</p>
      ) : (
        <div className="table-scroll">
          <table className="data">
            <thead>
              <tr>
                <th>Voo</th>
                {showCompany && <th>Companhia</th>}
                <th>Aeronave</th>
                <th>Stand</th>
                <th>Período</th>
                <th>Assistência em terra</th>
                <th>Estado</th>
                {action && <th />}
              </tr>
            </thead>
            <tbody>
              {sorted.map((r) => (
                <tr key={r.id} className={r.status === 'removed' ? 'struck' : undefined}>
                  <td className="num keep">{r.flightNumber}</td>
                  {showCompany && <td>{r.company}</td>}
                  <td>{aircraftLabel(r.aircraftType)}</td>
                  <td>{standLabel(r.standId)}</td>
                  <td className="num">{formatRange(r.start, r.end)}</td>
                  <td>{r.handler ?? 'Sem pedido'}</td>
                  <td className="keep">
                    <span className={`status ${r.status}`}>
                      {r.status === 'approved' ? 'Aprovado' : 'Removido pela ANA'}
                    </span>
                  </td>
                  {action && <td className="actions">{r.status === 'approved' ? action(r) : null}</td>}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  )
}
