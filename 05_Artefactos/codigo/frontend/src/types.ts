export type Role = 'despachante' | 'ana' | 'controlador' | 'handler'

export interface User {
  id: string
  name: string
  role: Role
  /** Airline for dispatchers, handling company for handlers. */
  company: string | null
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
  flightNumber: string
  company: string
  aircraftType: string
  /** ISO 8601 */
  start: string
  end: string
  status: ReservationStatus
  handler: string | null
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
  createdAt: string
}

export interface StandRequest {
  /** Client-generated. Sending the same id twice never creates a second reservation. */
  requestId: string
  /** The stand the dispatcher bids for. */
  standId: string
  flightNumber: string
  aircraftType: string
  start: string
  end: string
  handler: string | null
}
