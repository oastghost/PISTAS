import { useEffect, useState } from 'react'
import { formatDateTime } from '../format'
import type { Report, Stand } from '../types'

const ACK_KEY = 'pistas-acked-reports'

function loadAcked(): Set<string> {
  try {
    return new Set(JSON.parse(localStorage.getItem(ACK_KEY) ?? '[]') as string[])
  } catch {
    return new Set()
  }
}

function saveAcked(ids: Set<string>) {
  try {
    localStorage.setItem(ACK_KEY, JSON.stringify([...ids]))
  } catch {
    // acknowledgements then last until the page is closed
  }
}

interface Props {
  reports: Report[]
  stands: Stand[]
}

/**
 * Stays on screen until an operator acknowledges each report, so one that arrived while the
 * page was closed or in another tab is still seen. The same alert is also sent to every ANA
 * account by e-mail.
 */
export function ReportAlerts({ reports, stands }: Props) {
  const [acked, setAcked] = useState(loadAcked)
  const pending = reports.filter((r) => !acked.has(r.id)).sort((a, b) => Date.parse(b.createdAt) - Date.parse(a.createdAt))

  useEffect(() => {
    const base = document.title.replace(/^\(\d+\) /, '')
    document.title = pending.length > 0 ? `(${pending.length}) ${base}` : base
    return () => {
      document.title = base
    }
  }, [pending.length])

  function acknowledge(ids: string[]) {
    const next = new Set([...acked, ...ids])
    saveAcked(next)
    setAcked(next)
  }

  if (pending.length === 0) return null
  const standName = (id: string) => stands.find((s) => s.id === id)?.name ?? id

  return (
    <section className="panel alert" role="alert" aria-live="assertive">
      <div className="panel-head">
        <h2>
          {pending.length === 1 ? '1 reporte por tratar' : `${pending.length} reportes por tratar`}
        </h2>
        {pending.length > 1 && (
          <button type="button" className="small" onClick={() => acknowledge(pending.map((r) => r.id))}>
            Reconhecer todos
          </button>
        )}
      </div>
      <div className="table-scroll">
        <table className="data">
          <thead>
            <tr>
              <th>Matrícula</th>
              <th>Aeronave</th>
              <th>Stand</th>
              <th>Descrição</th>
              <th>Reportado por</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {pending.map((r) => (
              <tr key={r.id}>
                <td className="num">
                  <strong>{r.registration}</strong>
                </td>
                <td>{r.aircraftType}</td>
                <td>{standName(r.standId)}</td>
                <td>{r.text}</td>
                <td>
                  {r.author}
                  <br />
                  <span className="muted">{formatDateTime(r.createdAt)}</span>
                </td>
                <td>
                  <button type="button" className="small" onClick={() => acknowledge([r.id])}>
                    Reconhecer
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  )
}
