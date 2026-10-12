import type { ReactNode } from 'react'
import { formatRange } from '../format'
import type { AircraftType, Reservation, Stand } from '../types'

interface Props {
  reservations: Reservation[]
  stands: Stand[]
  aircraft: AircraftType[]
  empty: string
  /** Extra last column, e.g. a remove button. */
  action?: (reservation: Reservation) => ReactNode
  showCompany?: boolean
}

export function ReservationTable({ reservations, stands, aircraft, empty, action, showCompany = true }: Props) {
  if (reservations.length === 0) return <p className="muted">{empty}</p>
  const standLabel = (id: string) => {
    const s = stands.find((x) => x.id === id)
    return s ? `${s.name} (cat. ${s.category})` : id
  }
  const aircraftLabel = (code: string) => {
    const a = aircraft.find((x) => x.code === code)
    return a ? `${a.label} (cat. ${a.category})` : code
  }
  const sorted = [...reservations].sort((a, b) => Date.parse(a.start) - Date.parse(b.start))

  return (
    <table>
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
              <td>{r.flightNumber}</td>
              {showCompany && <td>{r.company}</td>}
              <td>{aircraftLabel(r.aircraftType)}</td>
              <td>{standLabel(r.standId)}</td>
              <td>{formatRange(r.start, r.end)}</td>
              <td>{r.handler ?? 'Sem pedido'}</td>
              <td>
                <span className={`badge ${r.status}`}>{r.status === 'approved' ? 'Aprovado' : 'Removido pela ANA'}</span>
              </td>
              {action && <td>{r.status === 'approved' ? action(r) : null}</td>}
            </tr>
          ))}
        </tbody>
      </table>
  )
}
