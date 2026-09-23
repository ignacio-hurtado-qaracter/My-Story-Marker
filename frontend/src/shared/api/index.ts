// Public surface of shared/api. Spec 002, FR-API-02 and FR-API-04.
import type { components } from '../types/openapi'

export { api, createApiClient } from './client'
export { errorMessage, isNotFound, parseApiError } from './errors'
export type { ApiError } from './errors'

/** The generated schema types, e.g. `Schemas['HealthResponse']`. */
export type Schemas = components['schemas']
