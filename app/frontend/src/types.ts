export type Role = 'despachante' | 'ana' | 'ana_supervisor' | 'controlador' | 'handler'

export interface User {
  id: string
  name: string
  role: Role
  /** Airline for dispatchers, handling company for handlers. */
  company: string | null
  /** Set until the owner replaces the temporary password the supervisor gave them. */
  mustChangePassword?: boolean
  /** A dispatcher's flight numbers must start with one of these (RYR, FR). */
  flightPrefixes?: string[]
}

/** ICAO aerodrome reference code letter, derived from wingspan. */
export type Category = 'A' | 'B' | 'C' | 'D' | 'E' | 'F'

export interface Stand {
  id: string
  name: string
  /** Apron number as in the AIP, or "Temporária". */
  apron: string
  /** Critical aircraft as written in the AIP: a type name or "Code C". */
  critical: string
  category: Category
  /** Largest wingspan the stand accepts, in metres. */
  maxWingspanM: number
}

export interface AircraftType {
  code: string
  label: string
  category: Category
  wingspanM: number
}

export type ReservationStatus = 'approved' | 'removed'

export interface Reservation {
  id: string
  requestId: string
  standId: string
  /** The aircraft, for example CS-TNP. This is what the screens show. */
  registration: string
  /** The ARRIVAL flight. The aircraft leaves under another number. */
  flightNumber: string
  /** ICAO code of the airport the aircraft came from, for example LEMD. */
  origin: string
  company: string
  aircraftType: string
  /** ISO 8601 */
  start: string
  end: string
  status: ReservationStatus
  handler: string | null
  /** The dispatcher who made the request. */
  requestedBy?: string | null
}

export interface Notice {
  id: string
  reservationId: string
  company: string
  message: string
  createdAt: string
}

export interface Report {
  id: string
  reservationId: string
  text: string
  author: string
  registration: string
  flightNumber: string
  aircraftType: string
  standId: string
  createdAt: string
}

export interface StandRequest {
  /** Client-generated. Sending the same id twice never creates a second reservation. */
  requestId: string
  /** The stand the dispatcher bids for. */
  standId: string
  registration: string
  /** Arrival flight number. */
  flightNumber: string
  /** ICAO code of the origin airport. */
  origin: string
  aircraftType: string
  start: string
  end: string
  handler: string | null
}

export interface Airline {
  name: string
  /** Flight number prefixes only this airline may use. */
  prefixes: string[]
  dispatchers: number
  activeDispatchers: number
}

/** An account as the supervisor sees it. Never contains a password. */
export interface ManagedAccount {
  id: string
  username: string
  name: string
  email: string | null
  role: Role
  company: string | null
  active: boolean
}

export interface NewAccount {
  username: string
  name: string
  email: string
  role: 'despachante' | 'ana'
  /** Required for a dispatcher, empty for an ANA operator. */
  company: string | null
  /** Temporary password, at least 12 characters. */
  password: string
}

export interface AuditEntry {
  id: number
  at: string
  username: string | null
  action: string
  detail: string | null
}
