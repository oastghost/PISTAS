import { mockApi } from './mock'

// Single switch point: replace with the fetch-based client when the backend exists.
export const api = mockApi
export { ApiError } from './client'
