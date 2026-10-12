import { Fragment, useMemo, useState } from 'react'
import { dayStart, formatRange, toDateInput } from '../format'
import type { AircraftType, Reservation, Stand } from '../types'
import { FlightDialog } from './FlightDialog'

const ALL = '*'
const DAY_MS = 24 * 60 * 60 * 1000
const HOUR_TICKS = [0, 3, 6, 9, 12, 15, 18, 21, 24]

interface Props {
  stands: Stand[]
  aircraft: AircraftType[]
  reservations: Reservation[]
  /** Reservations of this company are highlighted. */
  highlightCompany?: string | null
  selectedId?: string | null
  /** Called when a flight is clicked, in addition to opening its details. */
  onSelect?(reservation: Reservation): void
  /** When set, stand names become buttons that choose that stand for a bid. */
  onPickStand?(stand: Stand): void
  pickedStandId?: string | null
  /** Stands for which this returns false are greyed out and cannot be picked. */
  canPick?(stand: Stand): boolean
}

const apronLabel = (a: string) => (a === 'Temporária' ? 'Apron temporário' : `Apron ${a}`)

/** One row per stand, time on the x axis. Only approved reservations are drawn. */
export function Timeline({
  stands,
  aircraft,
  reservations,
  highlightCompany,
  selectedId,
  onSelect,
  onPickStand,
  pickedStandId,
  canPick,
}: Props) {
  const [day, setDay] = useState(() => toDateInput(new Date()))
  const aprons = useMemo(() => [...new Set(stands.map((s) => s.apron))], [stands])
  // The first apron is shown by default. ALL shows every stand, grouped by apron.
  const [choice, setChoice] = useState<string>('')
  const apron = choice === ALL || aprons.includes(choice) ? choice : (aprons[0] ?? ALL)
  const visible = stands.filter((s) => apron === ALL || s.apron === apron)
  const from = dayStart(day).getTime()
  const [openId, setOpenId] = useState<string | null>(null)
  const open = reservations.find((r) => r.id === openId)

  const byStand = useMemo(() => {
    const map = new Map<string, Reservation[]>()
    for (const r of reservations) {
      if (r.status !== 'approved') continue
      const list = map.get(r.standId) ?? []
      list.push(r)
      map.set(r.standId, list)
    }
    return map
  }, [reservations])

  const approvedCount = (a: string) => {
    const ids = new Set(stands.filter((s) => a === ALL || s.apron === a).map((s) => s.id))
    return reservations.filter((r) => r.status === 'approved' && ids.has(r.standId)).length
  }

  return (
    <section className="card">
      <div className="card-head">
        <h2>Plano de stands</h2>
        <label className="inline">
          Dia
          <input type="date" value={day} onChange={(e) => e.target.value && setDay(e.target.value)} />
        </label>
      </div>

      <div className="tabs" role="tablist" aria-label="Apron">
        {[ALL, ...aprons].map((a) => (
          <button
            key={a}
            type="button"
            role="tab"
            aria-selected={a === apron}
            className={a === apron ? 'tab active' : 'tab'}
            onClick={() => setChoice(a)}
          >
            {a === ALL ? 'Todos' : apronLabel(a)}
            <span className="tab-count">{approvedCount(a)}</span>
          </button>
        ))}
      </div>

      <div className="timeline" role="table" aria-label="Plano de stands por hora">
        <div className="tl-row tl-axis" role="row">
          <div className="tl-label" role="columnheader">Stand</div>
          <div className="tl-track">
            {HOUR_TICKS.map((h) => (
              <span key={h} className="tl-tick" style={{ left: `${(h / 24) * 100}%` }}>
                {String(h % 24).padStart(2, '0')}h
              </span>
            ))}
          </div>
        </div>

        {visible.map((stand, i) => (
          <Fragment key={stand.id}>
            {apron === ALL && (i === 0 || visible[i - 1].apron !== stand.apron) && (
              <div className="tl-group">{apronLabel(stand.apron)}</div>
            )}
            <div className={stand.id === pickedStandId ? 'tl-row picked' : 'tl-row'} role="row">
              <div className="tl-label" role="rowheader">
                {onPickStand ? (
                  <button
                    type="button"
                    className="tl-pick"
                    disabled={canPick ? !canPick(stand) : false}
                    aria-pressed={stand.id === pickedStandId}
                    title={canPick && !canPick(stand) ? 'Este stand não aceita a aeronave escolhida' : 'Pedir este stand'}
                    onClick={() => onPickStand(stand)}
                  >
                    {stand.name}
                  </button>
                ) : (
                  stand.name
                )}
                <small>{stand.critical}</small>
              </div>
              <div className="tl-track" role="cell">
                {HOUR_TICKS.slice(1, -1).map((h) => (
                  <span key={h} className="tl-grid" style={{ left: `${(h / 24) * 100}%` }} />
                ))}
                {(byStand.get(stand.id) ?? []).map((r) => {
                  const start = Math.max(Date.parse(r.start), from)
                  const end = Math.min(Date.parse(r.end), from + DAY_MS)
                  if (end <= start) return null
                  const own = highlightCompany != null && r.company === highlightCompany
                  const classes = ['tl-block', own ? 'own' : '', r.id === selectedId ? 'selected' : '']
                    .filter(Boolean)
                    .join(' ')
                  return (
                    <button
                      key={r.id}
                      type="button"
                      className={classes}
                      style={{
                        left: `${((start - from) / DAY_MS) * 100}%`,
                        width: `${((end - start) / DAY_MS) * 100}%`,
                      }}
                      title={`${r.flightNumber} · ${r.company} · ${formatRange(r.start, r.end)}`}
                      onClick={() => {
                        onSelect?.(r)
                        setOpenId(r.id)
                      }}
                    >
                      {r.flightNumber}
                    </button>
                  )
                })}
              </div>
            </div>
          </Fragment>
        ))}
      </div>

      {open && (
        <FlightDialog
          reservation={open}
          stand={stands.find((s) => s.id === open.standId)}
          aircraft={aircraft.find((a) => a.code === open.aircraftType)}
          onClose={() => setOpenId(null)}
        />
      )}
    </section>
  )
}
