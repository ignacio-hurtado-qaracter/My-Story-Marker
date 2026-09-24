// The backend calls of bible/ and their server state. Spec 003, FR-BIBLE, "Features and data";
// plan decision Q12. Each feature makes its own calls (architecture rule 6), over the shared typed
// client (rule 7): the cast, the locations, and the chapters and scene records that appearances
// are computed from.
import { queryOptions, useQueries, useQuery, type UseQueryResult } from '@tanstack/react-query'

import { api, errorMessage, isNotFound, parseApiError } from '../shared/api'
import type { ApiError, Schemas } from '../shared/api'

export type Character = Schemas['Character']
export type Location = Schemas['Location']
export type Chapter = Schemas['Chapter']
export type Scene = Schemas['Scene']

/** The id grammar of `openapi.json` for `/cast/{id}` and `/canon/locations/{id}` (FR-STORE-05). */
const ENTITY_ID = /^[a-z0-9][a-z0-9_-]*$/

/** An id the backend would refuse with a 422 is never sent: the page shows not-found instead. */
export function isEntityId(id: string): boolean {
  return id.length <= 120 && ENTITY_ID.test(id)
}

/** A non-2xx answer, carrying its parsed body (spec 002, FR-API-04). */
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

export function fetchCastIds(): Promise<string[]> {
  return unwrap(api.GET('/cast'))
}

export function fetchCharacter(id: string): Promise<Character> {
  return unwrap(api.GET('/cast/{id}', { params: { path: { id } } }))
}

export async function fetchLocationIds(): Promise<string[]> {
  const index = await unwrap(api.GET('/canon/locations'))
  return index.ids
}

export function fetchLocation(id: string): Promise<Location> {
  return unwrap(api.GET('/canon/locations/{id}', { params: { path: { id } } }))
}

export async function fetchChapters(): Promise<Chapter[]> {
  try {
    const file = await unwrap(api.GET('/structure/chapters'))
    return file.chapters ?? []
  } catch (error) {
    // No structure file yet means no chapters: every scene is "Sin capítulo" (plan 002 C8).
    if (isNotFoundError(error)) {
      return []
    }
    throw error
  }
}

export function fetchSceneIds(): Promise<string[]> {
  return unwrap(api.GET('/scenes'))
}

export function fetchScene(id: string): Promise<Scene> {
  return unwrap(api.GET('/scenes/{id}', { params: { path: { id } } }))
}

// ---------- Server state ----------

/** One screen's data: loading, failed (with a retry of what failed), or loaded. */
export type Loadable<T> =
  | { status: 'pending' }
  | { status: 'error'; error: unknown; retry: () => void }
  | { status: 'success'; data: T }

function fromQuery<T>(query: UseQueryResult<T>): Loadable<T> {
  if (query.error !== null) {
    return {
      status: 'error',
      error: query.error,
      retry: () => {
        void query.refetch()
      },
    }
  }
  return query.data === undefined ? { status: 'pending' } : { status: 'success', data: query.data }
}

/** Many records as one: the first failure wins, and retry refetches every failed record. */
function combineRecords<T>(results: UseQueryResult<T>[]): Loadable<T[]> {
  const failed = results.filter((result) => result.error !== null)
  const first = failed[0]
  if (first !== undefined) {
    return {
      status: 'error',
      error: first.error,
      retry: () => {
        for (const result of failed) {
          void result.refetch()
        }
      },
    }
  }
  const data = results.flatMap((result) => (result.data === undefined ? [] : [result.data]))
  return data.length === results.length ? { status: 'success', data } : { status: 'pending' }
}

/** `second` once `first` has loaded; until then, `first`'s own state. */
function after<A, B>(first: Loadable<A>, second: Loadable<B>): Loadable<B> {
  return first.status === 'success' ? second : first
}

/** A loaded value transformed; the other states pass through. */
export function mapLoadable<A, B>(loadable: Loadable<A>, transform: (value: A) => B): Loadable<B> {
  return loadable.status === 'success' ? { status: 'success', data: transform(loadable.data) } : loadable
}

/** Both values once both have loaded; the first failure otherwise, then pending. */
export function bothLoadable<A, B>(first: Loadable<A>, second: Loadable<B>): Loadable<[A, B]> {
  if (first.status === 'error') return first
  if (second.status === 'error') return second
  if (first.status === 'pending' || second.status === 'pending') return { status: 'pending' }
  return { status: 'success', data: [first.data, second.data] }
}

const characterQuery = (id: string) =>
  queryOptions({ queryKey: ['bible', 'character', id], queryFn: () => fetchCharacter(id) })

const locationQuery = (id: string) =>
  queryOptions({ queryKey: ['bible', 'location', id], queryFn: () => fetchLocation(id) })

const sceneQuery = (id: string) => queryOptions({ queryKey: ['bible', 'scene', id], queryFn: () => fetchScene(id) })

/** One character's record. The caller has checked the id with `isEntityId`. */
export function useCharacter(id: string) {
  return useQuery(characterQuery(id))
}

/** One location's record. The caller has checked the id with `isEntityId`. */
export function useLocation(id: string) {
  return useQuery(locationQuery(id))
}

/** Every character's record, in the order `GET /cast` gives (sorted ids). */
export function useCharacters(): Loadable<Character[]> {
  const ids = useQuery({ queryKey: ['bible', 'cast'], queryFn: fetchCastIds })
  const records = useQueries({
    queries: (ids.data ?? []).map((id) => characterQuery(id)),
    combine: combineRecords,
  })
  return after(fromQuery(ids), records)
}

/** Every location's record, in the order `GET /canon/locations` gives (sorted ids). */
export function useLocations(): Loadable<Location[]> {
  const ids = useQuery({ queryKey: ['bible', 'locations'], queryFn: fetchLocationIds })
  const records = useQueries({
    queries: (ids.data ?? []).map((id) => locationQuery(id)),
    combine: combineRecords,
  })
  return after(fromQuery(ids), records)
}

export interface Story {
  chapters: Chapter[]
  scenes: Scene[]
}

/** What appearances are computed from: the chapters and every scene record (Q12). */
export function useStory(): Loadable<Story> {
  const chapters = fromQuery(useQuery({ queryKey: ['bible', 'chapters'], queryFn: fetchChapters }))
  const sceneIds = useQuery({ queryKey: ['bible', 'scene-ids'], queryFn: fetchSceneIds })
  const records = useQueries({
    queries: (sceneIds.data ?? []).map((id) => sceneQuery(id)),
    combine: combineRecords,
  })
  const scenes = after(fromQuery(sceneIds), records)
  return mapLoadable(bothLoadable(chapters, scenes), ([chapterList, sceneList]) => ({
    chapters: chapterList,
    scenes: sceneList,
  }))
}
