// Spec 018: logging in stores the token, every API call then carries it as a bearer header,
// and logging out forgets it.
import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, describe, expect, it } from 'vitest'

import { renderWithProviders } from '../../test/render'
import { http, server } from '../../test/server'
import { AppRoutes } from './routes'
import { getAuthToken, setAuthToken } from '../shared/api'

const TOKEN = 'dummy-test-token' // test only
const USER = { id: 'usr-test', email: 'ana@example.com' }

let novelsAuthorization: string | null = null

beforeEach(() => {
  novelsAuthorization = null
  server.use(
    http.get('/health', ({ response }) =>
      response(200).json({ status: 'ok', vector: 'available', embedding_model: 'm', store_root: '/s' }),
    ),
    http.post('/auth/login', ({ response }) =>
      response(200).json({ access_token: TOKEN, token_type: 'bearer', expires_in: 43200, user: USER }),
    ),
    http.get('/auth/me', ({ response }) => response(200).json(USER)),
    http.get('/novels', ({ request, response }) => {
      novelsAuthorization = request.headers.get('Authorization')
      return response(200).json([])
    }),
  )
})

afterEach(() => {
  setAuthToken(null)
})

describe('login (spec 018)', () => {
  // spec 018 / AC 6
  it('stores the token and sends it as a bearer header on the next API call', async () => {
    const user = userEvent.setup()
    renderWithProviders(<AppRoutes />, { route: '/login' })
    await user.type(screen.getByLabelText('Email'), USER.email)
    await user.type(screen.getByLabelText('Contraseña'), 'correct horse battery')
    await user.click(screen.getByRole('button', { name: 'Entrar' }))

    expect(await screen.findByText(USER.email)).toBeInTheDocument()
    expect(getAuthToken()).toBe(TOKEN)
    await screen.findByRole('button', { name: 'Salir' })
    await waitFor(() => {
      expect(novelsAuthorization).toBe(`Bearer ${TOKEN}`)
    })
  })

  // spec 018 / AC 7
  it('forgets the token on logout', async () => {
    setAuthToken(TOKEN)
    const user = userEvent.setup()
    renderWithProviders(<AppRoutes />, { route: '/' })
    await user.click(await screen.findByRole('button', { name: 'Salir' }))
    expect(getAuthToken()).toBeNull()
    expect(await screen.findByRole('heading', { level: 1, name: 'Entrar' })).toBeInTheDocument()
  })
})

