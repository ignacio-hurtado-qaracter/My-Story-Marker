// Public surface of shared/api. Spec 002, FR-API-02 and FR-API-04; spec 018 (session token).
import type { components } from '../types/openapi'

export { api, createApiClient, downloadFile } from './client'
export { getAuthToken, onUnauthorized, setAuthToken, subscribeAuthToken } from './auth-token'
export { errorMessage, isNotFound, parseApiError } from './errors'
export type { ApiError } from './errors'

/** The generated schema types, e.g. `Schemas['HealthResponse']`. */
export type Schemas = components['schemas']
