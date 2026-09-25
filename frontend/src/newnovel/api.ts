// The backend calls of newnovel/ (spec 020), over the shared typed client.
import { useMutation, useQuery } from '@tanstack/react-query'

import { api, errorMessage, parseApiError } from '../shared/api'
import type { Schemas } from '../shared/api'

export type BriefReport = Schemas['BriefReport']
export type GenerationStatus = Schemas['GenerationStatus']
export type GenerateAccepted = Schemas['GenerateAccepted']
type Brief = Schemas['GenerateRequest']['brief']

/** A 422 from `/novels/generate`: the brief's report, to show next to the fields. */
export class InvalidBriefError extends Error {
  constructor(readonly report: BriefReport) {
    super('La ficha tiene campos pendientes.')
  }
}

function isReport(value: unknown): value is BriefReport {
  return typeof value === 'object' && value !== null && 'valid' in value && 'missing' in value
}

/** Live validation of the brief on the review step; cached per brief content. */
export function useBriefReport(brief: Brief, enabled: boolean) {
  return useQuery({
    queryKey: ['newnovel', 'validate', JSON.stringify(brief)],
    enabled,
    placeholderData: (previous) => previous,
    staleTime: Infinity,
    queryFn: async () => {
      const { data, error, response } = await api.POST('/interview/validate', { body: brief })
      if (!response.ok || data === undefined) throw new Error(errorMessage(parseApiError(response.status, error)))
      return data
    },
  })
}

export function useGenerateNovel() {
  return useMutation({
    mutationFn: async (body: Schemas['GenerateRequest']): Promise<GenerateAccepted> => {
      const { data, error, response } = await api.POST('/novels/generate', { body })
      // The 422 body is the BriefReport under `detail` (not FastAPI's declared shape): narrowed here.
      const payload: unknown = error
      if (response.status === 422 && typeof payload === 'object' && payload !== null && 'detail' in payload) {
        const detail: unknown = payload.detail
        if (isReport(detail)) throw new InvalidBriefError(detail)
      }
      if (response.status === 429) {
        throw new Error('Ya hay dos novelas generándose. Espera a que termine una y vuelve a intentarlo.')
      }
      if (!response.ok || data === undefined) throw new Error(errorMessage(parseApiError(response.status, error)))
      return data
    },
  })
}

export const POLL_MS = 5000

export function isFinished(status: GenerationStatus['status'] | undefined): boolean {
  return status === 'published' || status === 'blocked' || status === 'stopped_error'
}

/** Polls a generation every 5 s until it is published, blocked or stopped. */
export function useGeneration(novelId: string) {
  return useQuery({
    queryKey: ['newnovel', 'generation', novelId],
    refetchInterval: (query) => (isFinished(query.state.data?.status) ? false : POLL_MS),
    queryFn: async () => {
      const { data, error, response } = await api.GET('/novels/{novel_id}/generation', {
        params: { path: { novel_id: novelId } },
      })
      if (!response.ok || data === undefined) throw new Error(errorMessage(parseApiError(response.status, error)))
      return data
    },
  })
}
