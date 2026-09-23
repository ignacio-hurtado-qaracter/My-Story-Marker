// The single typed API client, and the only module that calls fetch. Spec 002, FR-API-02.
// Every route and shape comes from the generated `paths`; features build on it in their `api.ts`.
import createClient from 'openapi-fetch'

import type { paths } from '../types/openapi'

/** A client on another base URL or fetch, for tests. The app uses `api`. */
export function createApiClient(baseUrl: string, fetchImpl?: typeof fetch) {
  return createClient<paths>(fetchImpl === undefined ? { baseUrl } : { baseUrl, fetch: fetchImpl })
}

/** FR-API-05: the browser calls `/api`, which Vite proxies to the backend in development. */
export const api = createApiClient('/api')
