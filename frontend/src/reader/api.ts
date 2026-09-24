// The backend calls of reader/, over the shared typed client (spec 014, contract K5).
// Every shape is the generated `Schemas[...]`; nothing here is hand-typed.
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import { api, errorMessage, parseApiError } from '../shared/api'
import type { Schemas } from '../shared/api'

export type NovelSummary = Schemas['NovelSummary']
export type NovelDetail = Schemas['NovelDetail']
export type VersionInfo = Schemas['VersionInfo']
export type ChapterIndex = Schemas['ChapterIndex']
export type ChapterDetail = Schemas['ChapterDetail']
export type ChangeJob = Schemas['ChangeJob']
export type ChangeRequest = Schemas['ChangeRequest']

interface ClientResult<T> {
  data?: T
  error?: unknown
  response: Response
}

async function unwrap<T>(request: Promise<ClientResult<T>>): Promise<T> {
  const { data, error, response } = await request
  if (!response.ok || data === undefined) {
    throw new Error(errorMessage(parseApiError(response.status, error)))
  }
  return data
}

export function useNovels() {
  return useQuery({ queryKey: ['reader', 'novels'], queryFn: () => unwrap(api.GET('/novels')) })
}

export function useNovel(novelId: string) {
  return useQuery({
    queryKey: ['reader', 'novel', novelId],
    queryFn: () => unwrap(api.GET('/novels/{novel_id}', { params: { path: { novel_id: novelId } } })),
  })
}

export function useChapterIndex(novelId: string, version: number) {
  return useQuery({
    queryKey: ['reader', 'index', novelId, version],
    queryFn: () =>
      unwrap(
        api.GET('/novels/{novel_id}/versions/{version}/chapters', {
          params: { path: { novel_id: novelId, version } },
        }),
      ),
  })
}

export function useChapter(novelId: string, version: number, n: number) {
  return useQuery({
    queryKey: ['reader', 'chapter', novelId, version, n],
    queryFn: () =>
      unwrap(
        api.GET('/novels/{novel_id}/versions/{version}/chapters/{n}', {
          params: { path: { novel_id: novelId, version, n } },
        }),
      ),
  })
}

export function useRequestChange(novelId: string) {
  return useMutation({
    mutationFn: (body: ChangeRequest) =>
      unwrap(api.POST('/novels/{novel_id}/changes', { params: { path: { novel_id: novelId } }, body })),
  })
}

const POLL_MS = 1500

function isSettled(job: ChangeJob | undefined): boolean {
  return job?.status === 'done' || job?.status === 'failed'
}

/** Polls a change job until it settles; a finished job refreshes the novel's versions. */
export function useChangeJob(novelId: string, jobId: string | null) {
  const queryClient = useQueryClient()
  return useQuery({
    queryKey: ['reader', 'change', novelId, jobId],
    enabled: jobId !== null,
    refetchInterval: (query) => (isSettled(query.state.data) ? false : POLL_MS),
    queryFn: async () => {
      const job = await unwrap(
        api.GET('/novels/{novel_id}/changes/{job_id}', {
          params: { path: { novel_id: novelId, job_id: jobId ?? '' } },
        }),
      )
      if (job.status === 'done') {
        await queryClient.invalidateQueries({ queryKey: ['reader', 'novel', novelId] })
      }
      return job
    },
  })
}

/** The PDF of a version, served by the backend (an ordinary link, not a fetch). */
export function pdfHref(novelId: string, version: number): string {
  return `/api/novels/${encodeURIComponent(novelId)}/versions/${String(version)}/pdf`
}
