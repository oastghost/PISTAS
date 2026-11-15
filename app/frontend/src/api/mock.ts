import type {
  Airline,
  AuditEntry,
  ManagedAccount,
  NewAccount,
  Notice,
  Report,
  Reservation,
  Stand,
  StandRequest,
  User,
} from '../types'
import { ApiError, type Api } from './client'
import { matchesPrefix } from '../format'
import { AIRCRAFT, STANDS } from './lppt'

/*
 * In-memory stand-in for the backend. Stands come from the eAIP via lppt.ts (see the
 * wingspan caveat there). The flights are invented, the passwords are demo values and the ANA
 * phone number is not real. It mirrors the rules the real backend
 * must enforce so the screens can be built against them.
 */

const TURNAROUND_MINUTES = 30 // provisional, still subject to change
const ANA_PHONE = '913 560 661'
const STORAGE_KEY = 'pistas-mock-state-v5'
const REGISTRATION = /^[A-Z0-9]{1,2}-?[A-Z0-9]{2,5}$/
const ICAO = /^[A-Z]{4}$/
const SESSION_KEY = 'pistas-mock-session'

interface Account extends User {
  username: string
  password: string
}

const ACCOUNTS: Account[] = [
  { id: 'u1', username: 'tap', password: 'demo', name: 'Despachante TAP', role: 'despachante', company: 'TAP' },
  { id: 'u2', username: 'easyjet', password: 'demo', name: 'Despachante easyJet', role: 'despachante', company: 'easyJet' },
  { id: 'u3', username: 'ana', password: 'demo', name: 'Operações ANA', role: 'ana', company: null },
  { id: 'u7', username: 'supervisor', password: 'demo', name: 'Supervisão ANA', role: 'ana_supervisor', company: null },
  { id: 'u4', username: 'atc', password: 'demo', name: 'Controlador de tráfego', role: 'controlador', company: null },
  { id: 'u5', username: 'menzies', password: 'demo', name: 'Menzies', role: 'handler', company: 'Menzies' },
  { id: 'u6', username: 'portway', password: 'demo', name: 'Portway', role: 'handler', company: 'Portway' },
]

const HANDLERS = ['Menzies', 'Portway']

interface State {
  reservations: Reservation[]
  notices: Notice[]
  reports: Report[]
  /** `${company}:${registration}` -> stand ids ANA removed that aircraft from. */
  removedFrom: Record<string, string[]>
}

function seed(): State {
  const midnight = new Date()
  midnight.setHours(0, 0, 0, 0)
  const at = (h: number, m = 0) => new Date(midnight.getTime() + (h * 60 + m) * 60000).toISOString()
  const make = (
    n: number, standId: string, registration: string, flightNumber: string, origin: string, company: string,
    aircraftType: string, start: string, end: string, handler: string | null,
  ): Reservation => ({
    id: `seed-${n}`, requestId: `seed-req-${n}`, standId, registration, flightNumber, origin, company,
    aircraftType, start, end, status: 'approved', handler,
  })
  return {
    reservations: [
      make(1, '114', 'CS-TNP', 'TP1021', 'LEMD', 'TAP', 'A320', at(6, 30), at(8, 15), 'Menzies'),
      make(2, '114', 'CS-TUA', 'TP1033', 'LFPG', 'TAP', 'A321', at(9, 0), at(11, 0), null),
      make(3, '115', 'OE-IZA', 'U25001', 'EGKK', 'easyJet', 'A320', at(7, 0), at(9, 30), 'Portway'),
      make(4, '142', 'CS-TOF', 'TP0201', 'SBGR', 'TAP', 'A330', at(10, 0), at(14, 0), 'Menzies'),
      make(5, '200', 'G-UZHK', 'U25044', 'EGLL', 'easyJet', 'A320', at(12, 0), at(13, 45), null),
      make(6, '108', 'CS-DJA', 'TP1580', 'LPPR', 'TAP', 'ATR72', at(15, 0), at(16, 30), 'Portway'),
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
/** Notice ids each mock user has dismissed. Memory only. */
const dismissed: Record<string, string[]> = {}

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
  const flightPrefixes = a.role === 'despachante' ? (airlinePrefixes[a.company ?? ''] ?? []) : []
  return { id: a.id, name: a.name, role: a.role, company: a.company, flightPrefixes }
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
  const banned = state.removedFrom[`${company}:${input.registration.trim().toUpperCase()}`] ?? []
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

  async changePassword(currentPassword, newPassword) {
    await delay()
    const account = requireUser()
    if (account.password !== currentPassword) {
      throw new ApiError('INVALID_CREDENTIALS', 'A palavra-passe atual está incorreta.')
    }
    if (newPassword.length < 12 || newPassword === currentPassword) {
      throw new ApiError('INVALID_INPUT', 'Dados do pedido inválidos.')
    }
    account.password = newPassword
    return publicUser(account)
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
    if (!REGISTRATION.test(input.registration.trim().toUpperCase()) || !ICAO.test(input.origin.trim().toUpperCase())) {
      throw new ApiError('INVALID_INPUT', 'Matrícula ou código ICAO de origem inválidos.')
    }
    if (!input.flightNumber.trim() || !aircraft || Number.isNaN(start) || Number.isNaN(end) || end <= start) {
      throw new ApiError('INVALID_INPUT', 'Dados do pedido inválidos.')
    }
    const prefixes = airlinePrefixes[company] ?? []
    if (!matchesPrefix(input.flightNumber, prefixes)) {
      throw new ApiError(
        'INVALID_INPUT',
        prefixes.length === 0
          ? 'A sua companhia ainda não tem prefixo de voo. Peça à supervisão da ANA para o definir.'
          : `O número de voo de ${company} tem de começar por ${prefixes.join(' ou ')} seguido de 1 a 4 algarismos (por exemplo ${prefixes[0]}1234).`,
      )
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
      registration: input.registration.trim().toUpperCase(),
      flightNumber: input.flightNumber.trim().toUpperCase(),
      origin: input.origin.trim().toUpperCase(),
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
    requireUser('ana', 'ana_supervisor')
    const target = state.reservations.find((r) => r.id === reservationId)
    if (!target || target.status === 'removed') {
      throw new ApiError('NOT_FOUND', 'Reserva não encontrada.')
    }
    // Removal and notice are written together, never one without the other.
    const key = `${target.company}:${target.registration}`
    const notice: Notice = {
      id: crypto.randomUUID(),
      reservationId: target.id,
      company: target.company,
      message:
        `A ANA removeu a alocação da aeronave ${target.registration} no ${standName(target.standId)}. ` +
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
    return state.notices.filter((n) => n.company === user.company && !(dismissed[user.id] ?? []).includes(n.id))
  },

  async dismissNotice(noticeId) {
    await delay()
    const user = requireUser('despachante')
    dismissed[user.id] = [...(dismissed[user.id] ?? []), noticeId]
  },

  async dismissAllNotices() {
    await delay()
    const user = requireUser('despachante')
    dismissed[user.id] = state.notices.filter((n) => n.company === user.company).map((n) => n.id)
  },

  async createReport(reservationId, text) {
    await delay()
    const user = requireUser('controlador')
    if (!text.trim()) throw new ApiError('INVALID_INPUT', 'Escreva a descrição do problema.')
    const reservation = state.reservations.find((r) => r.id === reservationId)
    if (!reservation) throw new ApiError('NOT_FOUND', 'Reserva não encontrada.')
    const report: Report = {
      id: crypto.randomUUID(),
      reservationId,
      text: text.trim(),
      author: user.name,
      registration: reservation.registration,
      flightNumber: reservation.flightNumber,
      aircraftType: reservation.aircraftType,
      standId: reservation.standId,
      createdAt: new Date().toISOString(),
    }
    state = { ...state, reports: [...state.reports, report] }
    save()
    return report
  },

  async listReports() {
    await delay()
    requireUser('ana', 'ana_supervisor', 'controlador')
    return state.reports
  },

  // Supervisor administration, kept in memory like the rest of the mock.
  async listAirlines() {
    await delay()
    requireUser('ana_supervisor')
    return airlineRows()
  },

  async createAirline(name, prefixes) {
    await delay()
    const user = requireUser('ana_supervisor')
    const clean = name.trim()
    if (clean.length < 2) throw new ApiError('INVALID_INPUT', 'Dados do pedido inválidos.')
    if (airlineNames.includes(clean)) throw new ApiError('CONFLICT', 'Já existe uma companhia com esse nome.')
    const wanted = [...new Set(prefixes.map((p) => p.trim().toUpperCase()))]
    if (wanted.length === 0 || wanted.some((p) => !/^[A-Z0-9]{2,3}$/.test(p))) {
      throw new ApiError('INVALID_INPUT', 'Dados do pedido inválidos.')
    }
    const taken = wanted.find((p) => Object.values(airlinePrefixes).some((list) => list.includes(p)))
    if (taken) throw new ApiError('CONFLICT', `O prefixo ${taken} já pertence a outra companhia.`)
    airlineNames.push(clean)
    airlinePrefixes[clean] = wanted
    audit(user, 'airline_created', `${clean} (${wanted.join(', ')})`)
    return { name: clean, prefixes: wanted, dispatchers: 0, activeDispatchers: 0 }
  },

  async addAirlinePrefix(name, prefix) {
    await delay()
    const user = requireUser('ana_supervisor')
    const p = prefix.trim().toUpperCase()
    if (!airlineNames.includes(name)) throw new ApiError('NOT_FOUND', 'Companhia não encontrada.')
    if (!/^[A-Z0-9]{2,3}$/.test(p)) throw new ApiError('INVALID_INPUT', 'Dados do pedido inválidos.')
    if (Object.values(airlinePrefixes).some((list) => list.includes(p))) {
      throw new ApiError('CONFLICT', `O prefixo ${p} já pertence a uma companhia.`)
    }
    airlinePrefixes[name] = [...(airlinePrefixes[name] ?? []), p].sort()
    audit(user, 'prefix_added', `${name}: ${p}`)
    return airlineRows().find((a) => a.name === name)!
  },

  async removeAirlinePrefix(name, prefix) {
    await delay()
    const user = requireUser('ana_supervisor')
    const list = airlinePrefixes[name] ?? []
    if (!list.includes(prefix)) throw new ApiError('NOT_FOUND', 'Prefixo não encontrado.')
    if (list.length === 1) throw new ApiError('INVALID_INPUT', 'Uma companhia tem de ter pelo menos um prefixo.')
    airlinePrefixes[name] = list.filter((p) => p !== prefix)
    audit(user, 'prefix_removed', `${name}: ${prefix}`)
    return airlineRows().find((a) => a.name === name)!
  },

  async listAccounts() {
    await delay()
    requireUser('ana_supervisor')
    return managed.map(({ password: _password, ...rest }) => rest)
  },

  async createAccount(input: NewAccount) {
    await delay()
    const user = requireUser('ana_supervisor')
    if (input.password.length < 12) throw new ApiError('INVALID_INPUT', 'Dados do pedido inválidos.')
    if (input.role === 'despachante' && !airlineNames.includes(input.company ?? '')) {
      throw new ApiError('INVALID_INPUT', 'Companhia desconhecida. Crie-a primeiro.')
    }
    if (managed.some((a) => a.username === input.username)) {
      throw new ApiError('CONFLICT', 'Esse nome de utilizador já existe.')
    }
    const account = { id: `m${managed.length + 1}`, username: input.username, name: input.name, email: input.email,
      role: input.role, company: input.role === 'despachante' ? input.company : null, active: true, password: input.password }
    managed.push(account)
    audit(user, 'user_created', `${input.username} (${input.role}, ${input.company ?? 'ANA'})`)
    const { password: _password, ...rest } = account
    return rest
  },

  async updateAccount(id, change) {
    await delay()
    const user = requireUser('ana_supervisor')
    const target = managed.find((a) => a.id === id)
    if (!target || !['despachante', 'ana'].includes(target.role)) throw new ApiError('NOT_FOUND', 'Conta não encontrada.')
    if (change.active !== undefined && change.active !== target.active) {
      target.active = change.active
      audit(user, change.active ? 'user_enabled' : 'user_disabled', target.username)
    }
    if (change.password !== undefined) {
      if (change.password.length < 12) throw new ApiError('INVALID_INPUT', 'Dados do pedido inválidos.')
      target.password = change.password
      audit(user, 'password_reset', target.username)
    }
    const { password: _password, ...rest } = target
    return rest
  },

  async listAudit() {
    await delay()
    requireUser('ana_supervisor')
    return [...auditLog].reverse()
  },
}

type ManagedRow = ManagedAccount & { password: string }

const airlineNames = ['TAP', 'easyJet']
const airlinePrefixes: Record<string, string[]> = { TAP: ['TAP', 'TP'], easyJet: ['EZY', 'U2'] }
const managed: ManagedRow[] = [
  { id: 'm0', username: 'tap', name: 'Despachante TAP', email: 'tap@pistas.test', role: 'despachante', company: 'TAP', active: true, password: 'demo' },
  { id: 'm00', username: 'easyjet', name: 'Despachante easyJet', email: 'easyjet@pistas.test', role: 'despachante', company: 'easyJet', active: true, password: 'demo' },
  { id: 'm000', username: 'ana', name: 'Operações ANA', email: 'ana@pistas.test', role: 'ana', company: null, active: true, password: 'demo' },
]
const auditLog: AuditEntry[] = []

function audit(user: Account, action: string, detail: string) {
  auditLog.push({ id: auditLog.length + 1, at: new Date().toISOString(), username: user.username, action, detail })
}

function airlineRows(): Airline[] {
  return airlineNames.map((name) => {
    const mine = managed.filter((a) => a.role === 'despachante' && a.company === name)
    return {
      name,
      prefixes: airlinePrefixes[name] ?? [],
      dispatchers: mine.length,
      activeDispatchers: mine.filter((a) => a.active).length,
    }
  })
}

function standName(standId: string) {
  return STANDS.find((s) => s.id === standId)?.name ?? standId
}
