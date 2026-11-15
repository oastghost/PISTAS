import { useEffect, useId, useMemo, useRef, useState } from 'react'

const MINUTE_STEP = 5
const HOURS = Array.from({ length: 24 }, (_, h) => h)
const WEEKDAYS = ['seg', 'ter', 'qua', 'qui', 'sex', 'sáb', 'dom']

const monthFmt = new Intl.DateTimeFormat('pt-PT', { month: 'long', year: 'numeric' })
const dayFmt = new Intl.DateTimeFormat('pt-PT', { weekday: 'short', day: 'numeric', month: 'short' })

const pad = (n: number) => String(n).padStart(2, '0')
const startOfDay = (d: Date) => new Date(d.getFullYear(), d.getMonth(), d.getDate())
const sameDay = (a: Date, b: Date) => a.toDateString() === b.toDateString()

interface Props {
  label: string
  /** Milliseconds since the epoch. */
  value: number
  onChange(value: number): void
  /** Earlier days cannot be picked. Defaults to today. */
  minDay?: number
}

/** A day picker (calendar popover with Today and Tomorrow shortcuts) plus hour and minute lists. */
export function DateTimeField({ label, value, onChange, minDay }: Props) {
  const date = new Date(value)
  const [open, setOpen] = useState(false)
  const [shown, setShown] = useState(() => new Date(date.getFullYear(), date.getMonth(), 1))
  const box = useRef<HTMLDivElement>(null)
  const popupId = useId()

  const today = startOfDay(new Date())
  const floor = startOfDay(new Date(Math.max(minDay ?? 0, today.getTime())))
  const tomorrow = new Date(today.getFullYear(), today.getMonth(), today.getDate() + 1)

  useEffect(() => {
    if (!open) return
    const close = (e: Event) => {
      if (e instanceof KeyboardEvent ? e.key === 'Escape' : !box.current?.contains(e.target as Node)) setOpen(false)
    }
    document.addEventListener('mousedown', close)
    document.addEventListener('keydown', close)
    return () => {
      document.removeEventListener('mousedown', close)
      document.removeEventListener('keydown', close)
    }
  }, [open])

  // Monday-first grid of the shown month, padded with the neighbouring days.
  const cells = useMemo(() => {
    const first = new Date(shown.getFullYear(), shown.getMonth(), 1)
    const lead = (first.getDay() + 6) % 7
    return Array.from({ length: 42 }, (_, i) => new Date(first.getFullYear(), first.getMonth(), 1 - lead + i))
  }, [shown])

  function setDay(day: Date) {
    const next = new Date(value)
    next.setFullYear(day.getFullYear(), day.getMonth(), day.getDate())
    onChange(next.getTime())
  }

  function setTime(hour: number, minute: number) {
    const next = new Date(value)
    next.setHours(hour, minute, 0, 0)
    onChange(next.getTime())
  }

  const minutes = useMemo(() => {
    const list = Array.from({ length: 60 / MINUTE_STEP }, (_, i) => i * MINUTE_STEP)
    return list.includes(date.getMinutes()) ? list : [...list, date.getMinutes()].sort((a, b) => a - b)
  }, [date])

  const canGoBack = new Date(shown.getFullYear(), shown.getMonth(), 0) >= floor

  return (
    <div className="dtf" ref={box}>
      <span className="dtf-label">{label}</span>
      <div className="dtf-row">
        <button
          type="button"
          className="dtf-date"
          aria-haspopup="dialog"
          aria-expanded={open}
          aria-controls={popupId}
          onClick={() => {
            setShown(new Date(date.getFullYear(), date.getMonth(), 1))
            setOpen((o) => !o)
          }}
        >
          <svg viewBox="0 0 20 20" width="16" height="16" aria-hidden="true">
            <path
              d="M5 2v2M15 2v2M3 7h14M4.5 4h11A1.5 1.5 0 0 1 17 5.500v10a1.500 1.500 0 0 1-1.500 1.500h-11A1.500 1.500 0 0 1 3 15.500v-10A1.500 1.500 0 0 1 4.500 4Z"
              fill="none"
              stroke="currentColor"
              strokeWidth="1.5"
              strokeLinecap="round"
            />
          </svg>
          {dayFmt.format(date)}
        </button>
        <div className="dtf-time">
          <select aria-label={`${label}, hora`} value={date.getHours()} onChange={(e) => setTime(Number(e.target.value), date.getMinutes())}>
            {HOURS.map((h) => (
              <option key={h} value={h}>
                {pad(h)}
              </option>
            ))}
          </select>
          <span aria-hidden="true">:</span>
          <select aria-label={`${label}, minutos`} value={date.getMinutes()} onChange={(e) => setTime(date.getHours(), Number(e.target.value))}>
            {minutes.map((m) => (
              <option key={m} value={m}>
                {pad(m)}
              </option>
            ))}
          </select>
        </div>
      </div>
      <div className="dtf-quick">
        <button type="button" className="chip" aria-pressed={sameDay(date, today)} onClick={() => setDay(today)}>
          Hoje
        </button>
        <button type="button" className="chip" aria-pressed={sameDay(date, tomorrow)} onClick={() => setDay(tomorrow)}>
          Amanhã
        </button>
      </div>

      {open && (
        <div className="dtf-pop" id={popupId} role="dialog" aria-label={`${label}, escolher dia`}>
          <div className="dtf-month">
            <button
              type="button"
              className="icon"
              aria-label="Mês anterior"
              disabled={!canGoBack}
              onClick={() => setShown(new Date(shown.getFullYear(), shown.getMonth() - 1, 1))}
            >
              ‹
            </button>
            <strong>{monthFmt.format(shown)}</strong>
            <button
              type="button"
              className="icon"
              aria-label="Mês seguinte"
              onClick={() => setShown(new Date(shown.getFullYear(), shown.getMonth() + 1, 1))}
            >
              ›
            </button>
          </div>
          <div className="dtf-grid" role="grid">
            {WEEKDAYS.map((w) => (
              <span key={w} className="dtf-wd" role="columnheader">
                {w}
              </span>
            ))}
            {cells.map((day) => {
              const inMonth = day.getMonth() === shown.getMonth()
              const classes = ['dtf-day', inMonth ? '' : 'outside', sameDay(day, today) ? 'today' : '']
                .filter(Boolean)
                .join(' ')
              return (
                <button
                  key={day.getTime()}
                  type="button"
                  role="gridcell"
                  className={classes}
                  aria-selected={sameDay(day, date)}
                  disabled={day < floor}
                  onClick={() => {
                    setDay(day)
                    setOpen(false)
                  }}
                >
                  {day.getDate()}
                </button>
              )
            })}
          </div>
        </div>
      )}
    </div>
  )
}
