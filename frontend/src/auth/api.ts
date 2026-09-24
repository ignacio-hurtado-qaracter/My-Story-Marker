// The backend calls of auth/ (spec 018), over the shared typed client.
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useSyncExternalStore } from 'react'

import { api, errorMessage, getAuthToken, parseApiError, setAuthToken, subscribeAuthToken } from '../shared/api'
import type { Schemas } from '../shared/api'

export type Credentials = Schemas['Credentials']
export type Mode = 'login' | 'register'

/** The current token, re-rendering when it changes. */
export function useAuthToken(): string | null {
  return useSyncExternalStore(subscribeAuthToken, getAuthToken, getAuthToken)
}

function failure(status: number, error: unknown, mode: Mode): Error {
  if (mode === 'login' && status === 401) return new Error('Email o contraseña incorrectos.')
  if (mode === 'register' && status === 409) return new Error('Ese email ya está registrado.')
  return new Error(errorMessage(parseApiError(status, error)))
}

/** Log in or register; on success the token is stored and every cached query refetched. */
export function useAuthenticate(mode: Mode) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async (body: Credentials) => {
      const { data, error, response } =
        mode === 'login' ? await api.POST('/auth/login', { body }) : await api.POST('/auth/register', { body })
      if (!response.ok || data === undefined) throw failure(response.status, error, mode)
      return data
    },
    onSuccess: async (data) => {
      setAuthToken(data.access_token)
      await queryClient.invalidateQueries()
    },
  })
}

/** Who the token belongs to; only asked while logged in. */
export function useMe(token: string | null) {
  return useQuery({
    queryKey: ['auth', 'me', token],
    enabled: token !== null,
    queryFn: async () => {
      const { data, error, response } = await api.GET('/auth/me')
      if (!response.ok || data === undefined) throw new Error(errorMessage(parseApiError(response.status, error)))
      return data
    },
  })
}

/** Forget the token and every cached answer that was fetched with it. */
export function useLogout(): () => void {
  const queryClient = useQueryClient()
  return () => {
    setAuthToken(null)
    queryClient.clear()
  }
}
