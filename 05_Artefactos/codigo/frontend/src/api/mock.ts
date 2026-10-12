import type {
  Notice,
  Report,
  Reservation,
  Stand,
  StandRequest,
  User,
} from '../types'
import { ApiError, type Api } from './client'
import { AIRCRAFT, STANDS } from './lppt'

/*
 * In-memory stand-in for the backend. Stands come from the eAIP via lppt.ts (see the
 * wingspan caveat there). The flights are invented, the passwords are demo values and the ANA
 * phone number is not real. It mirrors the rules the real backend
 * must enforce so the screens can be built against them.
 */

const TURNAROUND_MINUTES = 30 // provisional, still subject to change
const ANA_PHONE = '+351 000 000 000 (simulado)'
const STORAGE_KEY = 'pistas-mock-state-v4'
const SESSION_KEY = 'pistas-mock-session'

interface Account extends User {
  username: string
  password: string
}

const ACCOUNTS: Account[] = [
  { id: 'u1', username: 'tap', password: 'demo', name: 'Despachante TAP', role: 'despachante', company: 'TAP' },
  { id: 'u2', username: 'easyjet', password: 'demo', name: 'Despachante easyJet', role: 'despachante', company: 'easyJet' },
  { id: 'u3', username: 'ana', password: 'demo', name: 'Operações ANA', role: 'ana', company: null },
  { id: 'u4', username: 'atc', password: 'demo', name: 'Controlador de tráfego', role: 'controlador', company: null },
  { id: 'u5', username: 'menzies', password: 'demo', name: 'Menzies', role: 'handler', company: 'Menzies' },
  { id: 'u6', username: 'portway', password: 'demo', name: 'Portway', role: 'handler', company: 'Portway' },
]

const HANDLERS = ['Menzies', 'Portway']

interface State {
  reservations: Reservation[]
  notices: Notice[]
  reports: Report[]
  /** `${company}:${flightNumber}` -> stand ids ANA removed that flight from. */
  removedFrom: Record<string, string[]>
}

function seed(): State {
  const midnight = new Date()
  midnight.setHours(0, 0, 0, 0)
  const at = (h: number, m = 0) => new Date(midnight.getTime() + (h * 60 + m) * 60000).toISOString()
  const make = (
    n: number, standId: string, flightNumber: string, company: string,
    aircraftType: string, start: string, end: string, handler: string | null,
  ): Reservation => ({
    id: `seed-${n}`, requestId: `seed-req-${n}`, standId, flightNumber, company,
    aircraftType, start, end, status: 'approved', handler,
  })
  return {
    reservations: [
      make(1, '114', 'TP1021', 'TAP', 'A320', at(6, 30), at(8, 15), 'Menzies'),
      make(2, '114', 'TP1033', 'TAP', 'A321', at(9, 0), at(11, 0), null),
      make(3, '115', 'U25001', 'easyJet', 'A320', at(7, 0), at(9, 30), 'Portway'),
      make(4, '142', 'TP0201', 'TAP', 'A330', at(10, 0), at(14, 0), 'Menzies'),
      make(5, '200', 'U25044', 'easyJet', 'A320', at(12, 0), at(13, 45), null),
      make(6, '108', 'TP1580', 'TAP', 'ATR72', at(15, 0), at(16, 30), 'Portway'),
    ],
    notices: [],
    reports: [],
    removedFrom: {},
  }
}

function load(): State {
  try {
    const raw = sessionStorage.getItem(STORAGE_KEY)
    if (raw) return JSON.parse(raw) as State
  } catch {
    // storage unavailable: start from the seed
  }
  return seed()
}

let state = load()

function save() {
  try {
    sessionStorage.setItem(STORAGE_KEY, JSON.stringify(state))
  } catch {
    // storage unavailable: state lives in memory only
  }
}

const delay = () => new Promise<void>((resolve) => setTimeout(resolve, 150))

let session: Account | null = null
try {
  const id = sessionStorage.getItem(SESSION_KEY)
  session = ACCOUNTS.find((a) => a.id === id) ?? null
} catch {
  session = null
}

function publicUser(a: Account): User {
  return { id: a.id, name: a.name, role: a.role, company: a.company }
}

function requireUser(...roles: User['role'][]): Account {
  if (!session) throw new ApiError('FORBIDDEN', 'Sessão expirada. Inicie sessão novamente.')
  if (roles.length > 0 && !roles.includes(session.role)) {
    throw new ApiError('FORBIDDEN', 'Não tem permissão para esta ação.')
  }
  return session
}

function overlaps(aStart: number, aEnd: number, bStart: number, bEnd: number) {
  return aStart < bEnd && bStart < aEnd
}

function isFree(stand: Stand, input: StandRequest, company: string): boolean {
  const gap = TURNAROUND_MINUTES * 60000
  const start = Date.parse(input.start)
  const end = Date.parse(input.end)
  const banned = state.removedFrom[`${company}:${input.flightNumber.trim().toUpperCase()}`] ?? []
  if (banned.includes(stand.id)) return false
  return !state.reservations.some(
    (r) =>
      r.status === 'approved' &&
      r.standId === stand.id &&
      overlaps(start - gap, end + gap, Date.parse(r.start), Date.parse(r.end)),
  )
}

/**
 * Stand-in for the CSP solver: free stands the aircraft fits, same apron as the wanted stand
 * first, then the tightest fit so large stands stay free for large aircraft.
 */
function proposals(input: StandRequest, company: string, wingspanM: number): Stand[] {
  const wanted = STANDS.find((s) => s.id === input.standId)
  return STANDS.filter((s) => s.id !== input.standId && s.maxWingspanM >= wingspanM && isFree(s, input, company))
    .sort(
      (a, b) =>
        Number(b.apron === wanted?.apron) - Number(a.apron === wanted?.apron) ||
        a.maxWingspanM - b.maxWingspanM,
    )
    .slice(0, 5)
}

export const mockApi: Api = {
  async login(username, password) {
    await delay()
    const account = ACCOUNTS.find((a) => a.username === username.trim().toLowerCase())
    if (!account || account.password !== password) {
      throw new ApiError('INVALID_CREDENTIALS', 'Utilizador ou palavra-passe incorretos.')
    }
    session = account
    try {
      sessionStorage.setItem(SESSION_KEY, account.id)
    } catch {
      // session lives in memory only
    }
    return publicUser(account)
  },

  async logout() {
    session = null
    try {
      sessionStorage.removeItem(SESSION_KEY)
    } catch {
      // nothing to clear
    }
  },

  async currentUser() {
    return session ? publicUser(session) : null
  },

  async listStands() {
    await delay()
    requireUser()
    return STANDS
  },

  async listAircraftTypes() {
    requireUser()
    return AIRCRAFT
  },

  async listHandlers() {
    requireUser()
    return HANDLERS
  },

  async listReservations() {
    await delay()
    requireUser()
    return state.reservations
  },

  async requestStand(input) {
    await delay()
    const user = requireUser('despachante')
    const company = user.company ?? ''

    // Idempotency: the same request id returns the first result and creates nothing.
    const existing = state.reservations.find((r) => r.requestId === input.requestId)
    if (existing) return existing

    const aircraft = AIRCRAFT.find((a) => a.code === input.aircraftType)
    const start = Date.parse(input.start)
    const end = Date.parse(input.end)
    if (!input.flightNumber.trim() || !aircraft || Number.isNaN(start) || Number.isNaN(end) || end <= start) {
      throw new ApiError('INVALID_INPUT', 'Dados do pedido inválidos.')
    }
    if (input.handler && !HANDLERS.includes(input.handler)) {
      throw new ApiError('INVALID_INPUT', 'Empresa de assistência em terra desconhecida.')
    }

    const stand = STANDS.find((s) => s.id === input.standId)
    if (!stand) throw new ApiError('INVALID_INPUT', 'Stand desconhecido.')
    if (stand.maxWingspanM < aircraft.wingspanM) {
      throw new ApiError('STAND_TOO_SMALL', `O ${stand.name} não aceita esta aeronave (limite ${stand.critical}).`)
    }
    if (!isFree(stand, input, company)) {
      throw new ApiError('STAND_UNAVAILABLE', `O ${stand.name} não está disponível neste período.`)
    }

    const reservation: Reservation = {
      id: crypto.randomUUID(),
      requestId: input.requestId,
      standId: stand.id,
      flightNumber: input.flightNumber.trim().toUpperCase(),
      company,
      aircraftType: input.aircraftType,
      start: new Date(start).toISOString(),
      end: new Date(end).toISOString(),
      status: 'approved',
      handler: input.handler,
    }
    state = { ...state, reservations: [...state.reservations, reservation] }
    save()
    return reservation
  },

  async suggestStands(input) {
    await delay()
    const user = requireUser('despachante')
    const aircraft = AIRCRAFT.find((a) => a.code === input.aircraftType)
    if (!aircraft || Number.isNaN(Date.parse(input.start)) || Number.isNaN(Date.parse(input.end))) {
      throw new ApiError('INVALID_INPUT', 'Dados do pedido inválidos.')
    }
    return proposals(input, user.company ?? '', aircraft.wingspanM)
  },

  async removeReservation(reservationId) {
    await delay()
    requireUser('ana')
    const target = state.reservations.find((r) => r.id === reservationId)
    if (!target || target.status === 'removed') {
      throw new ApiError('NOT_FOUND', 'Reserva não encontrada.')
    }
    // Removal and notice are written together, never one without the other.
    const key = `${target.company}:${target.flightNumber}`
    const notice: Notice = {
      id: crypto.randomUUID(),
      reservationId: target.id,
      company: target.company,
      message:
        `A ANA removeu a alocação do voo ${target.flightNumber} no ${standName(target.standId)}. ` +
        `Para esclarecimentos contacte a ANA: ${ANA_PHONE}.`,
      createdAt: new Date().toISOString(),
    }
    state = {
      ...state,
      reservations: state.reservations.map((r) => (r.id === target.id ? { ...r, status: 'removed' } : r)),
      notices: [...state.notices, notice],
      removedFrom: { ...state.removedFrom, [key]: [...(state.removedFrom[key] ?? []), target.standId] },
    }
    save()
  },

  async listNotices() {
    await delay()
    const user = requireUser('despachante')
    return state.notices.filter((n) => n.company === user.company)
  },

  async createReport(reservationId, text) {
    await delay()
    const user = requireUser('controlador')
    if (!text.trim()) throw new ApiError('INVALID_INPUT', 'Escreva a descrição do problema.')
    if (!state.reservations.some((r) => r.id === reservationId)) {
      throw new ApiError('NOT_FOUND', 'Reserva não encontrada.')
    }
    const report: Report = {
      id: crypto.randomUUID(),
      reservationId,
      text: text.trim(),
      author: user.name,
      createdAt: new Date().toISOString(),
    }
    state = { ...state, reports: [...state.reports, report] }
    save()
    return report
  },

  async listReports() {
    await delay()
    requireUser('ana', 'controlador')
    return state.reports
  },
}

function standName(standId: string) {
  return STANDS.find((s) => s.id === standId)?.name ?? standId
}
