// The app-wide providers: the query cache and a top-level error boundary. Spec 002, FR-SHELL-01.
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { Component, useState, type ReactNode } from 'react'

import { ErrorPanel } from '../shared/ui'

interface BoundaryProps {
  children: ReactNode
}

interface BoundaryState {
  hasError: boolean
}

// The last line of defence: a render error anywhere below shows the error panel, not a blank page.
// Screens show their own request errors; this catches what they do not.
class AppErrorBoundary extends Component<BoundaryProps, BoundaryState> {
  override state: BoundaryState = { hasError: false }

  static getDerivedStateFromError(): BoundaryState {
    return { hasError: true }
  }

  reset = () => {
    this.setState({ hasError: false })
  }

  override render() {
    if (this.state.hasError) {
      return <ErrorPanel message="Algo ha fallado al mostrar esta página." onRetry={this.reset} />
    }
    return this.props.children
  }
}

export function Providers({ children }: { children: ReactNode }) {
  // One cache per app instance, created on first render and kept for its lifetime.
  const [queryClient] = useState(() => new QueryClient())
  return (
    <QueryClientProvider client={queryClient}>
      <AppErrorBoundary>{children}</AppErrorBoundary>
    </QueryClientProvider>
  )
}
