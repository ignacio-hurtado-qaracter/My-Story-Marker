// The backend calls of scenes/, over the shared typed client. Spec 002, FR-SCN, FR-API-04.
// Scene records, the chapter structure and drafts are read by no other feature yet (rule 6).
import { api, errorMessage, isNotFound, parseApiError } from '../shared/api'
import type { ApiError, Schemas } from '../shared/api'

/** The scene-id pattern of `openapi.json` for `/scenes/{id}` and `/manuscript/{id}`. */
const SCENE_ID = /^\d{3}$/

/** FR-SCN-06: an id the backend would refuse with a 422 is never sent. */
export function isSceneId(id: string): boolean {
  return SCENE_ID.test(id)
}

/** A non-2xx answer, carrying its parsed body (FR-API-04). */
export class ApiRequestError extends Error {
  readonly apiError: ApiError

  constructor(apiError: ApiError) {
    super(errorMessage(apiError))
    this.name = 'ApiRequestError'
    this.apiError = apiError
  }
}

/** What an error panel shows for any failure: the parsed API message, or a network message. */
export function describeError(error: unknown): string {
  return error instanceof ApiRequestError ? errorMessage(error.apiError) : 'No se pudo contactar con el servidor'
}

export function isNotFoundError(error: unknown): boolean {
  return error instanceof ApiRequestError && isNotFound(error.apiError)
}

interface ClientResult<T> {
  data?: T
  error?: unknown
  response: Response
}

async function unwrap<T>(request: Promise<ClientResult<T>>): Promise<T> {
  const { data, error, response } = await request
  if (!response.ok || data === undefined) {
    throw new ApiRequestError(parseApiError(response.status, error))
  }
  return data
}

export async function fetchChapters(): Promise<Schemas['Chapter'][]> {
  try {
    const file = await unwrap(api.GET('/structure/chapters'))
    return file.chapters ?? []
  } catch (error) {
    // A book with no structure file yet has no chapters; that is the empty state, not an error.
    if (isNotFoundError(error)) {
      return []
    }
    throw error
  }
}

export function fetchSceneIds(): Promise<string[]> {
  return unwrap(api.GET('/scenes'))
}

export function fetchScene(id: string): Promise<Schemas['Scene']> {
  return unwrap(api.GET('/scenes/{id}', { params: { path: { id } } }))
}

/** FR-SCN-02: a scene without a draft is the empty state, so a 404 is `null`, not an error. */
export async function fetchDraft(id: string): Promise<Schemas['Draft'] | null> {
  try {
    return await unwrap(api.GET('/manuscript/{id}', { params: { path: { id } } }))
  } catch (error) {
    if (isNotFoundError(error)) {
      return null
    }
    throw error
  }
}
