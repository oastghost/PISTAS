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

/** True when the flight number is one of the prefixes plus 1 to 4 digits and an optional letter. */
export function matchesPrefix(flight: string, prefixes: string[]): boolean {
  const f = flight.trim().toUpperCase()
  return prefixes.some((p) => new RegExp(`^${p}\\d{1,4}[A-Z]?$`).test(f))
}

export const HOUR_MS = 60 * 60 * 1000

/** Tail registration such as CS-TNP, D-AIUA or N123AB. */
export const isRegistration = (v: string) => /^[A-Z0-9]{1,2}-?[A-Z0-9]{2,5}$/.test(v.trim().toUpperCase())

/** ICAO airport code: four letters. */
export const isIcao = (v: string) => /^[A-Z]{4}$/.test(v.trim().toUpperCase())

/** Airports that most often send aircraft to Lisbon, offered as suggestions only. */
export const COMMON_ORIGINS: [string, string][] = [
  ['LPPR', 'Porto'], ['LPFR', 'Faro'], ['LPMA', 'Funchal'], ['LPPD', 'Ponta Delgada'],
  ['LEMD', 'Madrid'], ['LEBL', 'Barcelona'], ['LEPA', 'Palma de Maiorca'], ['LFPG', 'Paris CDG'],
  ['LFPO', 'Paris Orly'], ['EGLL', 'Londres Heathrow'], ['EGKK', 'Londres Gatwick'], ['EGSS', 'Londres Stansted'],
  ['EHAM', 'Amesterdão'], ['EDDF', 'Frankfurt'], ['EDDM', 'Munique'], ['LSZH', 'Zurique'],
  ['LIRF', 'Roma Fiumicino'], ['LIMC', 'Milão Malpensa'], ['EBBR', 'Bruxelas'], ['EIDW', 'Dublin'],
  ['LGAV', 'Atenas'], ['LTFM', 'Istambul'], ['GCLP', 'Gran Canaria'], ['GMMN', 'Casablanca'],
  ['SBGR', 'São Paulo'], ['SBGL', 'Rio de Janeiro'], ['KEWR', 'Newark'], ['KJFK', 'Nova Iorque JFK'],
  ['FNLU', 'Luanda'], ['GVAC', 'Ilha do Sal'],
]

export const ROLE_LABEL = {
  despachante: 'Despachante',
  ana: 'ANA',
  ana_supervisor: 'Supervisão ANA',
  controlador: 'Controlador',
  handler: 'Ground handler',
} as const
