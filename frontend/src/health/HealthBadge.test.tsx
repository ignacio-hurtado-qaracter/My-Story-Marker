// The health badge of spec 002, FR-HLT-01: its three states and its 30 s polling limit (AC 7).
import { act, screen } from '@testing-library/react'
import { HttpResponse } from 'msw'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { renderWithProviders } from '../../test/render'
import { http, server } from '../../test/server'
import { HealthBadge } from './HealthBadge'

const healthy = { status: 'ok', vector: 'available', embedding_model: 'm', store_root: '/s' }

/** Serves a healthy /health and returns a function reading how many requests it has seen. */
function serveHealthy(body = healthy): () => number {
  let requests = 0
  server.use(
    http.get('/health', ({ response }) => {
      requests += 1
      return response(200).json(body)
    }),
  )
  return () => requests
}

function badge(): HTMLElement {
  return screen.getByRole('status', { name: 'Estado del backend' })
}

afterEach(() => {
  vi.useRealTimers()
})

describe('HealthBadge', () => {
  // spec 002 / AC 7
  it('shows "comprobando…" while the first request is in flight', async () => {
    serveHealthy()
    renderWithProviders(<HealthBadge />)
    expect(badge()).toHaveTextContent('comprobando…')
    // Let the request settle so it does not outlive the test.
    expect(await screen.findByText(/vector: available/)).toBeInTheDocument()
  })

  // spec 002 / AC 7
  it.each([
    ['available', healthy],
    ['unavailable', { ...healthy, vector: 'unavailable' }],
  ])('shows ok and vector: %s from /health', async (vector, body) => {
    serveHealthy(body)
    renderWithProviders(<HealthBadge />)
    expect(await screen.findByText(`ok · vector: ${vector}`)).toBeInTheDocument()
    expect(badge()).toHaveTextContent(`ok · vector: ${vector}`)
  })

  // spec 002 / AC 7
  it('shows "backend no disponible" on a network error', async () => {
    server.use(http.get('/health', ({ response }) => response.untyped(HttpResponse.error())))
    renderWithProviders(<HealthBadge />)
    expect(await screen.findByText('backend no disponible')).toBeInTheDocument()
  })

  // spec 002 / AC 7
  it('shows "backend no disponible" on a 502 with a non-JSON body', async () => {
    server.use(
      http.get('/health', ({ response }) =>
        response.untyped(
          new HttpResponse('<html><body>Bad Gateway</body></html>', {
            status: 502,
            headers: { 'Content-Type': 'text/html' },
          }),
        ),
      ),
    )
    renderWithProviders(<HealthBadge />)
    expect(await screen.findByText('backend no disponible')).toBeInTheDocument()
  })

  // spec 002 / AC 7
  it('issues no second request before 30 s, and polls again after', async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true })
    const requests = serveHealthy()
    renderWithProviders(<HealthBadge />)
    expect(await screen.findByText('ok · vector: available')).toBeInTheDocument()
    expect(requests()).toBe(1)

    await act(() => vi.advanceTimersByTimeAsync(29_000))
    expect(requests()).toBe(1)

    await act(() => vi.advanceTimersByTimeAsync(1_500))
    await vi.waitFor(() => {
      expect(requests()).toBe(2)
    })
  })
})
