import type { AircraftType, Notice, Report, Reservation, Stand, StandRequest, User } from '../types'
import { ApiError, type Api, type ApiErrorCode } from './client'

/** Talks to the FastAPI backend. The Vite dev server and nginx both forward /api to it. */

const TOKEN_KEY = 'pistas-token'

let token: string | null = null
try {
  token = sessionStorage.getItem(TOKEN_KEY)
} catch {
  token = null
}

let sessionExpiredListener: (() => void) | null = null

/** Called when the backend says the session is gone, so the app can go back to the login. */
export function onSessionExpired(listener: () => void) {
  sessionExpiredListener = listener
}

function setToken(value: string | null) {
  token = value
  try {
    if (value) sessionStorage.setItem(TOKEN_KEY, value)
    else sessionStorage.removeItem(TOKEN_KEY)
  } catch {
    // the token then lives in memory only
  }
}

interface ErrorBody {
  code?: string
  message?: string
}

async function call<T>(method: string, path: string, body?: unknown): Promise<T> {
  let response: Response
  try {
    response = await fetch(`/api${path}`, {
      method,
      headers: {
        ...(body !== undefined ? { 'Content-Type': 'application/json' } : {}),
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
      },
      body: body !== undefined ? JSON.stringify(body) : undefined,
    })
  } catch {
    throw new ApiError('UNAVAILABLE', 'Sem ligação ao servidor. Tente novamente dentro de instantes.')
  }

  if (response.ok) {
    return response.status === 204 ? (undefined as T) : ((await response.json()) as T)
  }

  let error: ErrorBody = {}
  try {
    error = (await response.json()) as ErrorBody
  } catch {
    // not JSON, for example a gateway error page
  }
  const code = (error.code ?? (response.status >= 500 ? 'UNAVAILABLE' : 'INVALID_INPUT')) as ApiErrorCode
  if (code === 'SESSION_EXPIRED') {
    setToken(null)
    sessionExpiredListener?.()
  }
  throw new ApiError(code, error.message ?? 'Ocorreu um erro inesperado.')
}

export const httpApi: Api = {
  async login(username, password) {
    const result = await call<{ token: string; user: User }>('POST', '/auth/login', { username, password })
    setToken(result.token)
    return result.user
  },

  async logout() {
    setToken(null)
  },

  async currentUser() {
    if (!token) return null
    try {
      return await call<User>('GET', '/auth/me')
    } catch (e) {
      if (e instanceof ApiError && e.code === 'SESSION_EXPIRED') return null
      throw e
    }
  },

  listStands: () => call<Stand[]>('GET', '/stands'),
  listAircraftTypes: () => call<AircraftType[]>('GET', '/aircraft-types'),
  listHandlers: () => call<string[]>('GET', '/handlers'),
  listReservations: () => call<Reservation[]>('GET', '/reservations'),

  requestStand: (input: StandRequest) => call<Reservation>('POST', '/reservations', input),
  suggestStands: (input: StandRequest) => call<Stand[]>('POST', '/reservations/suggestions', input),
  removeReservation: (reservationId) => call<void>('DELETE', `/reservations/${reservationId}`),
  listNotices: () => call<Notice[]>('GET', '/notices'),

  createReport: (reservationId, text) => call<Report>('POST', '/reports', { reservationId, text }),
  listReports: () => call<Report[]>('GET', '/reports'),
}
