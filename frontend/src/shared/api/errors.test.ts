// The error parser of FR-API-04. The real-404 half of AC 6 is frontend/e2e/api-error.spec.ts.
import { describe, expect, it } from 'vitest'

import { errorMessage, isNotFound, parseApiError } from './errors'

describe('parseApiError', () => {
  // spec 002 / AC 6
  it('reads an IF-07 body as a harness error, keeping error, detail and context', () => {
    const body = { error: 'not_found', detail: 'scene 999 does not exist', kind: 'scene', id: '999' }
    expect(parseApiError(404, body)).toEqual({
      kind: 'harness',
      status: 404,
      error: 'not_found',
      detail: 'scene 999 does not exist',
      context: { kind: 'scene', id: '999' },
    })
  })

  // spec 002 / AC 6
  it('reads an IF-07 body that arrives as unparsed text', () => {
    const e = parseApiError(503, '{"error":"index_busy","detail":"rebuilding"}')
    expect(e).toMatchObject({ kind: 'harness', error: 'index_busy', detail: 'rebuilding' })
  })

  it('prefers IF-07 on a 422, since InvalidRecord is a 422 with a string detail', () => {
    const e = parseApiError(422, { error: 'invalid_record', detail: 'bad field', file: 'x.yaml' })
    expect(e.kind).toBe('harness')
  })

  it('reads a FastAPI validation body as a validation error', () => {
    const detail = [{ loc: ['path', 'id'], msg: 'String should match pattern', type: 'string_pattern_mismatch' }]
    expect(parseApiError(422, { detail })).toEqual({ kind: 'validation', status: 422, detail })
  })

  it.each([
    ['undefined', undefined],
    ['null', null],
    ['an empty body', ''],
    ['an HTML page', '<html><body>Bad Gateway</body></html>'],
    ['an unrecognised object', { foo: 1 }],
    ['a detail that is a number', { detail: 42 }],
    ['a detail list with a malformed item', { detail: [{ msg: 'no loc' }] }],
    ['an error code without a detail', { error: 'not_found' }],
    ['a JSON array', [1, 2]],
  ])('reads %s as unknown, keeping only the status', (_label, body) => {
    expect(parseApiError(502, body)).toEqual({ kind: 'unknown', status: 502 })
  })
})

describe('errorMessage', () => {
  it('shows the IF-07 detail', () => {
    expect(errorMessage(parseApiError(404, { error: 'not_found', detail: 'no such scene' }))).toBe(
      'no such scene',
    )
  })

  it('shows a generic message with the status for a validation error', () => {
    const e = parseApiError(422, { detail: [{ loc: ['query'], msg: 'bad', type: 'value_error' }] })
    expect(errorMessage(e)).toBe('Petición no válida (HTTP 422)')
  })

  it('shows a generic message with the status for an unknown body', () => {
    expect(errorMessage(parseApiError(500, 'Internal Server Error'))).toBe('Error del servidor (HTTP 500)')
  })
})

describe('isNotFound', () => {
  it('is true for any 404, whatever the body', () => {
    expect(isNotFound(parseApiError(404, { error: 'not_found', detail: 'x' }))).toBe(true)
    expect(isNotFound(parseApiError(404, ''))).toBe(true)
  })

  it('is false for other statuses', () => {
    expect(isNotFound(parseApiError(422, { detail: [] }))).toBe(false)
    expect(isNotFound(parseApiError(500, undefined))).toBe(false)
  })
})
