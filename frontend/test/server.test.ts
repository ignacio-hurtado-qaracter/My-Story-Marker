// The test harness itself: the typed MSW server serves what a handler declares, and the types
// reject a handler the backend's schema does not allow. Spec 002, plan step 4.
import { HttpResponse } from 'msw'
import { describe, expect, it } from 'vitest'

import { api } from '../src/shared/api'
import { http, server } from './server'

describe('typed MSW server', () => {
  it('serves a typed handler to the app client', async () => {
    server.use(
      http.get('/health', ({ response }) =>
        response(200).json({ status: 'ok', vector: 'available', embedding_model: 'm', store_root: '/s' }),
      ),
    )
    const { data } = await api.GET('/health')
    expect(data?.vector).toBe('available')
  })

  it('serves an undeclared status through response.untyped', async () => {
    server.use(
      http.get('/scenes/{id}', ({ response }) =>
        response.untyped(HttpResponse.json({ error: 'not_found', detail: 'no scene 999' }, { status: 404 })),
      ),
    )
    const { response } = await api.GET('/scenes/{id}', { params: { path: { id: '999' } } })
    expect(response.status).toBe(404)
  })

  // spec 002 / AC 17. These handlers are never registered: they exist for `tsc -b`, which must
  // reject both. Each `@ts-expect-error` fails the typecheck if its line ever compiles cleanly,
  // so deleting either directive makes `npm run typecheck` fail (rule 15).
  it('rejects, at type level, an unpublished route and a wrongly shaped response', () => {
    const planted = [
      // @ts-expect-error spec 002 / AC 17: the backend publishes no /not-a-route.
      http.get('/not-a-route', () => new HttpResponse(null, { status: 200 })),
      http.get('/health', ({ response }) =>
        // @ts-expect-error spec 002 / AC 17: HealthResponse.status is a string, not a number.
        response(200).json({ status: 1, vector: 'available', embedding_model: 'm', store_root: '/s' }),
      ),
    ]
    expect(planted).toHaveLength(2)
  })
})
