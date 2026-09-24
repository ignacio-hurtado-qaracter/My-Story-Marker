// The session token (spec 018): kept in memory and mirrored to localStorage so a reload keeps
// the session. Storage can be missing or throw (private mode, blocked site data), so every
// access is wrapped and the in-memory copy stays the source of truth.
// shared/api owns it because the API client is what attaches it (FR-API-02); the auth/
// feature only sets and clears it.

const STORAGE_KEY = 'msm.auth.token'

let memory: string | null | undefined
const tokenListeners = new Set<() => void>()
const unauthorizedListeners = new Set<() => void>()

function readStorage(): string | null {
  try {
    return globalThis.localStorage.getItem(STORAGE_KEY)
  } catch {
    return null
  }
}

function writeStorage(token: string | null): void {
  try {
    if (!token) globalThis.localStorage.removeItem(STORAGE_KEY)
    else globalThis.localStorage.setItem(STORAGE_KEY, token)
  } catch {
    // Storage unavailable: the session lasts as long as the page.
  }
}

/** The current token, or null when logged out. */
export function getAuthToken(): string | null {
  memory ??= readStorage()
  return memory
}

/** Store (or, with null, clear) the token and tell the subscribers. */
export function setAuthToken(token: string | null): void {
  memory = token
  writeStorage(token)
  for (const listener of tokenListeners) listener()
}

/** For `useSyncExternalStore`: called whenever the token changes. */
export function subscribeAuthToken(listener: () => void): () => void {
  tokenListeners.add(listener)
  return () => tokenListeners.delete(listener)
}

/** Called by the client on every 401, so the app can send the reader to the login page. */
export function onUnauthorized(listener: () => void): () => void {
  unauthorizedListeners.add(listener)
  return () => unauthorizedListeners.delete(listener)
}

export function notifyUnauthorized(): void {
  for (const listener of unauthorizedListeners) listener()
}

/** `Authorization: Bearer <token>` when logged in, else nothing. */
export function authHeaders(): Record<string, string> {
  const token = getAuthToken()
  return token === null ? {} : { Authorization: `Bearer ${token}` }
}
