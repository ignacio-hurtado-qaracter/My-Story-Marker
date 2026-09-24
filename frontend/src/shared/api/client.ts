// The single typed API client, and the only module that calls fetch. Spec 002, FR-API-02.
// Every route and shape comes from the generated `paths`; features build on it in their `api.ts`.
// Spec 018: every request carries the session token, and a 401 is reported to the app.
import createClient, { type Middleware } from 'openapi-fetch'

import type { paths } from '../types/openapi'
import { authHeaders, notifyUnauthorized } from './auth-token'

// Looked up on every call, not captured once: a test's MSW server patches the global fetch after
// this module has been imported.
const callGlobalFetch = (request: Request): Promise<Response> => globalThis.fetch(request)

const auth: Middleware = {
  onRequest({ request }) {
    for (const [name, value] of Object.entries(authHeaders())) request.headers.set(name, value)
    return request
  },
  onResponse({ response }) {
    if (response.status === 401) notifyUnauthorized()
    return response
  },
}

/** A client on another base URL or fetch, for tests. The app uses `api`. */
export function createApiClient(baseUrl: string, fetchImpl: (request: Request) => Promise<Response> = callGlobalFetch) {
  const client = createClient<paths>({ baseUrl, fetch: fetchImpl })
  client.use(auth)
  return client
}

/**
 * FR-API-05: the browser calls `/api` on its own origin, which Vite proxies to the backend in
 * development. Absolute, because Node's fetch (under Vitest) does not resolve relative URLs.
 */
export const api = createApiClient(`${window.location.origin}/api`)

/**
 * Download a file the API serves (the PDF) with the session token. A plain `<a href download>`
 * cannot send the `Authorization` header, so the file is fetched and handed to the browser.
 */
export async function downloadFile(href: string, filename: string): Promise<void> {
  const response = await globalThis.fetch(href, { headers: authHeaders() })
  if (response.status === 401) notifyUnauthorized()
  if (!response.ok) throw new Error(`HTTP ${String(response.status)}`)
  const url = URL.createObjectURL(await response.blob())
  const link = document.createElement('a')
  link.href = url
  link.download = filename
  link.click()
  URL.revokeObjectURL(url)
}
