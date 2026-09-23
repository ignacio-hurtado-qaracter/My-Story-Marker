// Render a component the way the app does: inside a fresh query cache and a router.
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, type RenderResult } from '@testing-library/react'
import type { ReactElement } from 'react'
import { MemoryRouter } from 'react-router'

export interface RenderOptions {
  /** The URL the router starts at. */
  route?: string
}

export function renderWithProviders(ui: ReactElement, { route = '/' }: RenderOptions = {}): RenderResult {
  // No retries in tests: an error state must show on the first failure.
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false, gcTime: Infinity } },
  })
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={[route]}>{ui}</MemoryRouter>
    </QueryClientProvider>,
  )
}
