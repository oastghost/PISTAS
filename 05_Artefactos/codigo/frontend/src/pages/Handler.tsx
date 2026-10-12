import { useAuth } from '../auth'
import { ReservationTable } from '../components/ReservationTable'
import { usePlan } from '../hooks'

export function Handler() {
  const { user } = useAuth()
  const plan = usePlan()
  const mine = (plan.data?.reservations ?? []).filter((r) => r.handler === user?.company)

  return (
    <div className="stack">
      <h1>Pedidos de assistência em terra</h1>
      <p className="muted">
        Vista só de leitura. A PISTAS não atribui equipas: a distribuição pelas equipas é feita internamente por cada
        empresa. Pedidos cujo stand foi removido pela ANA aparecem como cancelados.
      </p>
      {plan.error && <p className="alert error">{plan.error}</p>}
      {plan.data && (
        <section className="card">
          <h2>{user?.company}</h2>
          <ReservationTable
            reservations={mine}
            stands={plan.data.stands}
            aircraft={plan.data.aircraft}
            empty="Sem pedidos de assistência."
          />
        </section>
      )}
    </div>
  )
}
