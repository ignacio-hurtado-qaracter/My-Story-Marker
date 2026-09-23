// The backend health badge that app/'s layout places. Spec 002, FR-HLT-01; AC 7.
// States: loading, error, loaded. Empty does not apply: /health always answers with a body.
import { useQuery } from '@tanstack/react-query'

import { fetchHealth } from './api'
import { StatusBadge } from './StatusBadge'

// FR-HLT-01: no more than one request per 30 s. Nothing else may add one: no retries, and no
// refetch on window focus or reconnect. A failure shows at once and is retried by the next poll.
const POLL_INTERVAL_MS = 30_000

const LABEL = 'Estado del backend'

export function HealthBadge() {
  const { data, isPending, isError } = useQuery({
    queryKey: ['health'],
    queryFn: fetchHealth,
    refetchInterval: POLL_INTERVAL_MS,
    staleTime: POLL_INTERVAL_MS,
    retry: false,
    refetchOnWindowFocus: false,
    refetchOnReconnect: false,
  })

  if (isPending) {
    return (
      <StatusBadge label={LABEL} tone="pending">
        comprobando…
      </StatusBadge>
    )
  }
  // A failed poll after a success is an error too: the backend is down now.
  if (isError) {
    return (
      <StatusBadge label={LABEL} tone="error">
        backend no disponible
      </StatusBadge>
    )
  }
  return (
    <StatusBadge label={LABEL} tone="ok">
      {data.status} · vector: {data.vector}
    </StatusBadge>
  )
}
