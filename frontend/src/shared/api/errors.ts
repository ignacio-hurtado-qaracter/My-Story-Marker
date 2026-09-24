// The one hand-written API type. Spec 002, FR-API-04.
// openapi.json declares only FastAPI's 422 body; the IF-07 body of spec 001 is not declared there
// (Decision R2-2), so a non-2xx body is narrowed here at runtime, never trusted by its type.
import type { components } from '../types/openapi'

type ValidationDetail = NonNullable<components['schemas']['HTTPValidationError']['detail']>
type ValidationItem = components['schemas']['ValidationError']

export type ApiError =
  // Spec 001, IF-07: `{"error": "<code>", "detail": "<message>", ...context}`.
  | {
      kind: 'harness'
      status: number
      error: string
      detail: string
      context: Record<string, unknown>
    }
  // FastAPI request validation: `{"detail": [ ... ]}`.
  | { kind: 'validation'; status: number; detail: ValidationDetail }
  // An empty, non-JSON or unrecognised body, e.g. the dev proxy with the backend down.
  | { kind: 'unknown'; status: number }

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value)
}

function isValidationItem(value: unknown): value is ValidationItem {
  return (
    isRecord(value) &&
    typeof value['msg'] === 'string' &&
    typeof value['type'] === 'string' &&
    Array.isArray(value['loc']) &&
    value['loc'].every((part) => typeof part === 'string' || typeof part === 'number')
  )
}

// openapi-fetch hands over a parsed JSON value, or the raw text when the body is not JSON.
function decode(body: unknown): unknown {
  if (typeof body !== 'string') {
    return body
  }
  try {
    return JSON.parse(body)
  } catch {
    return undefined
  }
}

/** Narrow the body of a non-2xx response to one of the three cases of `ApiError`. */
export function parseApiError(status: number, body: unknown): ApiError {
  const value = decode(body)
  if (!isRecord(value)) {
    return { kind: 'unknown', status }
  }
  const { error, detail, ...context } = value
  // IF-07 first: `InvalidRecord` is also a 422, and its `detail` is a string.
  if (typeof error === 'string' && typeof detail === 'string') {
    return { kind: 'harness', status, error, detail, context }
  }
  if (Array.isArray(detail) && detail.every(isValidationItem)) {
    return { kind: 'validation', status, detail }
  }
  return { kind: 'unknown', status }
}

/** What an error panel shows: the IF-07 message when there is one, else a generic message. */
export function errorMessage(e: ApiError): string {
  switch (e.kind) {
    case 'harness':
      return e.detail
    case 'validation':
      return `Petición no válida (HTTP ${String(e.status)})`
    case 'unknown':
      return `Error del servidor (HTTP ${String(e.status)})`
  }
}

export function isNotFound(e: ApiError): boolean {
  return e.status === 404
}
