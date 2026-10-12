import type { Role } from './types'

const HOME: Record<Role, string> = {
  despachante: '/despachante',
  ana: '/ana',
  controlador: '/controlador',
  handler: '/handler',
}

export const homePath = (role: Role) => HOME[role]
