// The backend calls of cover/, over the shared typed client, and their queries. Spec 003,
// FR-COVER-01 and FR-COVER-04; plan 003 Q10: the cover fetches the project record itself (each
// feature makes its own calls, architecture rule 6).
import { useQuery } from '@tanstack/react-query'

import { api, errorMessage, isNotFound, parseApiError } from '../shared/api'
import type { ApiError, Schemas } from '../shared/api'

/** A non-2xx answer, carrying its parsed body (spec 002, FR-API-04). */
export class CoverRequestError extends Error {
  readonly apiError: ApiError

  constructor(apiError: ApiError) {
    super(errorMessage(apiError))
    this.name = 'CoverRequestError'
    this.apiError = apiError
  }
}

interface ClientResult<T> {
  data?: T
  error?: unknown
  response: Response
}

async function unwrap<T>(request: Promise<ClientResult<T>>): Promise<T> {
  const { data, error, response } = await request
  if (!response.ok || data === undefined) {
    throw new CoverRequestError(parseApiError(response.status, error))
  }
  return data
}

export function fetchProject(): Promise<Schemas['Project']> {
  return unwrap(api.GET('/canon/project'))
}

/**
 * The id of the chapter the reader starts with: the first in file order, or `null` when the
 * book has no chapters yet. A missing structure file (404) is "no chapters", as on the index
 * (plan 002 C8); any other failure is an error.
 */
export async function fetchFirstChapterId(): Promise<string | null> {
  try {
    const file = await unwrap(api.GET('/structure/chapters'))
    return file.chapters?.[0]?.id ?? null
  } catch (error) {
    if (error instanceof CoverRequestError && isNotFound(error.apiError)) {
      return null
    }
    throw error
  }
}

/**
 * The premise is an extra (FR-COVER-04): on any failure the lead is left out. Retrying would
 * only keep its placeholder on screen, for a 404 in effect forever.
 */
export function useProject() {
  return useQuery({ queryKey: ['cover', 'project'], queryFn: fetchProject, retry: false })
}

/**
 * The target of "Empezar a leer". On failure the button falls back to the index, which shows
 * the error with its own retry, so the cover does not retry either.
 */
export function useFirstChapterId() {
  return useQuery({ queryKey: ['cover', 'first-chapter'], queryFn: fetchFirstChapterId, retry: false })
}
