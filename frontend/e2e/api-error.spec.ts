// A real 404 from the backend parses as the IF-07 case of ApiError. Spec 002, AC 6.
import { expect, test } from '@playwright/test'

import { errorMessage, isNotFound, parseApiError } from '../src/shared/api/errors'

// spec 002 / AC 6
test('ApiError parses the IF-07 body of a real 404', async ({ request }) => {
  const response = await request.get('/api/scenes/999')
  expect(response.status()).toBe(404)

  const parsed = parseApiError(response.status(), await response.text())
  expect(parsed.kind).toBe('harness')
  expect(isNotFound(parsed)).toBe(true)
  if (parsed.kind !== 'harness') throw new Error('unreachable')
  expect(parsed.error).toBe('not_found')
  expect(parsed.detail.length).toBeGreaterThan(0)
  expect(errorMessage(parsed)).toBe(parsed.detail)
})
