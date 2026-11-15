import type { Api } from './client'
import { httpApi } from './http'
import { mockApi } from './mock'

// The real backend by default. VITE_USE_MOCK=true runs the frontend alone with simulated data.
export const api: Api = import.meta.env.VITE_USE_MOCK === 'true' ? mockApi : httpApi
export { ApiError } from './client'
