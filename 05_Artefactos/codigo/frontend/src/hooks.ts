import { useCallback, useEffect, useState } from 'react'
import { api } from './api'
import type { AircraftType, Reservation, Stand } from './types'

export function errorMessage(e: unknown): string {
  return e instanceof Error ? e.message : 'Ocorreu um erro inesperado.'
}

interface Loaded<T> {
  data: T | null
  error: string | null
  loading: boolean
  reload(): void
}

export function useLoad<T>(fetcher: () => Promise<T>): Loaded<T> {
  const [data, setData] = useState<T | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)
  const [tick, setTick] = useState(0)

  useEffect(() => {
    let cancelled = false
    fetcher().then(
      (value) => {
        if (cancelled) return
        setData(value)
        setError(null)
        setLoading(false)
      },
      (e: unknown) => {
        if (cancelled) return
        setError(errorMessage(e))
        setLoading(false)
      },
    )
    return () => {
      cancelled = true
    }
    // The fetcher is a module-level API call; only `tick` should retrigger it.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [tick])

  const reload = useCallback(() => setTick((t) => t + 1), [])
  return { data, error, loading, reload }
}

export interface PlanData {
  stands: Stand[]
  reservations: Reservation[]
  aircraft: AircraftType[]
}

export function usePlan(): Loaded<PlanData> {
  return useLoad(async () => {
    const [stands, reservations, aircraft] = await Promise.all([
      api.listStands(),
      api.listReservations(),
      api.listAircraftTypes(),
    ])
    return { stands, reservations, aircraft }
  })
}
