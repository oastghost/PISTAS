import { useEffect, useRef } from 'react'
import { formatDateTime, formatTime } from '../format'
import type { AircraftType, Reservation, Stand } from '../types'

interface Props {
  reservation: Reservation
  stand: Stand | undefined
  aircraft: AircraftType | undefined
  onClose(): void
}

function duration(start: string, end: string): string {
  const minutes = Math.round((Date.parse(end) - Date.parse(start)) / 60000)
  const h = Math.floor(minutes / 60)
  const m = minutes % 60
  return [h > 0 ? `${h} h` : '', m > 0 ? `${m} min` : ''].filter(Boolean).join(' ')
}

export function FlightDialog({ reservation: r, stand, aircraft, onClose }: Props) {
  const ref = useRef<HTMLDialogElement>(null)

  useEffect(() => {
    ref.current?.showModal()
  }, [])

  return (
    <dialog
      ref={ref}
      className="flight-dialog"
      aria-labelledby="flight-dialog-title"
      onClose={onClose}
      onClick={(e) => {
        // A click on the backdrop lands on the dialog element itself.
        if (e.target === ref.current) ref.current?.close()
      }}
    >
      <div className="dialog-head">
        <h2 id="flight-dialog-title">Voo {r.flightNumber}</h2>
        <button type="button" className="ghost-dark" onClick={() => ref.current?.close()} aria-label="Fechar">
          ✕
        </button>
      </div>
      <dl className="details">
        <dt>Companhia aérea</dt>
        <dd>{r.company}</dd>

        <dt>Aeronave</dt>
        <dd>
          {aircraft ? aircraft.label : r.aircraftType}
          {aircraft && <small> · categoria {aircraft.category}</small>}
        </dd>

        <dt>Assistência em terra</dt>
        <dd>{r.handler ?? 'Sem pedido'}</dd>

        <dt>Tempo em terra</dt>
        <dd>
          {formatDateTime(r.start)} – {formatTime(r.end)}
          <small> · {duration(r.start, r.end)}</small>
        </dd>

        <dt>Stand</dt>
        <dd>
          {stand ? stand.name : r.standId}
          {stand && <small> · Apron {stand.apron} · {stand.critical}</small>}
        </dd>
      </dl>
    </dialog>
  )
}
