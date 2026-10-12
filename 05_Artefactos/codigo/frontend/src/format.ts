const timeFmt = new Intl.DateTimeFormat('pt-PT', { hour: '2-digit', minute: '2-digit' })
const dateTimeFmt = new Intl.DateTimeFormat('pt-PT', {
  day: '2-digit',
  month: '2-digit',
  hour: '2-digit',
  minute: '2-digit',
})

export const formatTime = (iso: string) => timeFmt.format(new Date(iso))
export const formatDateTime = (iso: string) => dateTimeFmt.format(new Date(iso))
export const formatRange = (start: string, end: string) => `${formatDateTime(start)} – ${formatTime(end)}`

/** Value for <input type="date"> in local time. */
export function toDateInput(d: Date): string {
  const p = (n: number) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())}`
}

/** Local midnight of a yyyy-mm-dd string. */
export function dayStart(dateInput: string): Date {
  const [y, m, d] = dateInput.split('-').map(Number)
  return new Date(y, m - 1, d)
}

export const ROLE_LABEL = {
  despachante: 'Despachante',
  ana: 'ANA',
  controlador: 'Controlador',
  handler: 'Ground handler',
} as const
