// expect: no-restricted-imports
// (e) planted: openapi-fetch outside src/shared/api/.
import createClient from 'openapi-fetch'

export const client = createClient({ baseUrl: '/api' })
