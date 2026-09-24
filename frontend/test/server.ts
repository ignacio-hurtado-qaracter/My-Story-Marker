// The typed MSW server for component tests. Spec 002, NFR-04; plan decision P4.
//
// `http` is typed by the generated `paths`: a handler for a route the backend does not publish,
// or a response of the wrong shape, fails `npm run typecheck` (AC 17). Statuses the schema does
// not declare, such as the IF-07 404, go through `response.untyped(...)`.
import { createOpenApiHttp } from 'openapi-msw'
import { setupServer } from 'msw/node'

import type { paths } from '../src/shared/types/openapi'

export const http = createOpenApiHttp<paths>({ baseUrl: '*/api' })

export const server = setupServer()
