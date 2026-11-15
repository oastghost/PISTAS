import type {
  AircraftType,
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

export type ApiErrorCode =
  | 'INVALID_CREDENTIALS'
  | 'SESSION_EXPIRED'
  | 'FORBIDDEN'
  | 'PASSWORD_CHANGE_REQUIRED'
  | 'NOT_FOUND'
  | 'CONFLICT'
  | 'INVALID_INPUT'
  | 'STAND_TOO_SMALL'
  | 'STAND_UNAVAILABLE'
  | 'UNAVAILABLE'

export class ApiError extends Error {
  code: ApiErrorCode

  constructor(code: ApiErrorCode, message: string) {
    super(message)
    this.code = code
  }
}

/**
 * The only contract the screens depend on. The mock implements it today and a
 * fetch-based client for the FastAPI backend replaces it later. Roles are enforced
 * by the backend; the screens hiding buttons is not security.
 */
export interface Api {
  login(username: string, password: string): Promise<User>
  logout(): Promise<void>
  currentUser(): Promise<User | null>
  /** Needs the current password. Clears mustChangePassword. */
  changePassword(currentPassword: string, newPassword: string): Promise<User>

  listStands(): Promise<Stand[]>
  listAircraftTypes(): Promise<AircraftType[]>
  listHandlers(): Promise<string[]>
  listReservations(): Promise<Reservation[]>

  /** Bid for one specific stand. Approved when it is free and the aircraft fits, refused otherwise. */
  requestStand(input: StandRequest): Promise<Reservation>
  /**
   * Alternatives for a refused bid, best first. The solver only proposes: nothing is written
   * and the dispatcher still has to bid for one of them.
   */
  suggestStands(input: StandRequest): Promise<Stand[]>
  removeReservation(reservationId: string): Promise<void>
  listNotices(): Promise<Notice[]>
  /** Hides one notice for the current dispatcher only. */
  dismissNotice(noticeId: string): Promise<void>
  /** Hides every current notice for the current dispatcher. */
  dismissAllNotices(): Promise<void>

  createReport(reservationId: string, text: string): Promise<Report>
  listReports(): Promise<Report[]>

  // Supervisor only: airlines and accounts. The backend refuses every other role.
  listAirlines(): Promise<Airline[]>
  createAirline(name: string, prefixes: string[]): Promise<Airline>
  addAirlinePrefix(name: string, prefix: string): Promise<Airline>
  removeAirlinePrefix(name: string, prefix: string): Promise<Airline>
  listAccounts(): Promise<ManagedAccount[]>
  createAccount(input: NewAccount): Promise<ManagedAccount>
  updateAccount(id: string, change: { active?: boolean; password?: string }): Promise<ManagedAccount>
  listAudit(): Promise<AuditEntry[]>
}
