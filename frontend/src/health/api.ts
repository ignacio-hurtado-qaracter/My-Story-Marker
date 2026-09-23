// The health feature's one call: GET /health through the shared client. Spec 002, FR-HLT-01.
import { api, errorMessage, parseApiError, type Schemas } from '../shared/api'

export type Health = Schemas['HealthResponse']

/** Resolves with the backend's health; rejects on any non-2xx, and on a network error. */
export async function fetchHealth(): Promise<Health> {
  const { data, error, response } = await api.GET('/health')
  if (data === undefined) {
    throw new Error(errorMessage(parseApiError(response.status, error)))
  }
  return data
}
