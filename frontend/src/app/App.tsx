// The application root: providers, the browser router and the route table. Spec 002, FR-SHELL-01.
import { BrowserRouter } from 'react-router'

// Spec 003, FR-TOK: the design tokens and base styles, once, as part of the global layout.
import '../shared/ui/tokens.css'
import '../shared/ui/base.css'

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
