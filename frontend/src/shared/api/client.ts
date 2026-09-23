// The single typed API client, and the only module that calls fetch. Spec 002, FR-API-02.
// Every route and shape comes from the generated `paths`; features build on it in their `api.ts`.
import createClient from 'openapi-fetch'

import type { paths } from '../types/openapi'

// Looked up on every call, not captured once: a test's MSW server patches the global fetch after
// this module has been imported.
const callGlobalFetch = (request: Request): Promise<Response> => globalThis.fetch(request)

/** A client on another base URL or fetch, for tests. The app uses `api`. */
export function createApiClient(baseUrl: string, fetchImpl: (request: Request) => Promise<Response> = callGlobalFetch) {
  return createClient<paths>({ baseUrl, fetch: fetchImpl })
}

/**
 * FR-API-05: the browser calls `/api` on its own origin, which Vite proxies to the backend in
 * development. Absolute, because Node's fetch (under Vitest) does not resolve relative URLs.
 */
export const api = createApiClient(`${window.location.origin}/api`)
