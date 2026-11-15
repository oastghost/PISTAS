import { useAuth } from '../auth'
import { ReservationTable } from '../components/ReservationTable'
import { Timeline } from '../components/Timeline'
import { usePlan } from '../hooks'

export function Handler() {
  const { user } = useAuth()
  const plan = usePlan()
  const mine = (plan.data?.reservations ?? []).filter((r) => r.handler === user?.company)

  return (
    <>
      <div className="page-head">
        <h1>Pedidos de assistência em terra</h1>
        <p>
          Vista só de leitura. A distribuição pelas equipas é feita internamente pela {user?.company}. Pedidos de
          voos retirados do stand pela ANA aparecem como removidos.
        </p>
      </div>
      {plan.error && (
        <p className="msg error" role="alert">
          {plan.error}
        </p>
      )}
      {plan.data && (
        <div className="stack">
          <Timeline
            stands={plan.data.stands}
            aircraft={plan.data.aircraft}
            reservations={mine}
            highlightCompany={null}
          />
          <ReservationTable
            title={`Pedidos para ${user?.company ?? ''}`}
            reservations={mine}
            stands={plan.data.stands}
            aircraft={plan.data.aircraft}
            empty="Sem pedidos de assistência."
          />
        </div>
      )}
    </>
  )
}
