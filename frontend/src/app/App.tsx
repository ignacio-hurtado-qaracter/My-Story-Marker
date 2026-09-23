// The application root: providers, the browser router and the route table. Spec 002, FR-SHELL-01.
import { BrowserRouter } from 'react-router'

import { Providers } from './providers'
import { AppRoutes } from './routes'

export function App() {
  return (
    <Providers>
      <BrowserRouter>
        <AppRoutes />
      </BrowserRouter>
    </Providers>
  )
}
