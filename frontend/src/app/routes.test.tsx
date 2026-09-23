// app/'s route table and providers. Spec 002, FR-SHELL-01 and FR-SHELL-03 (AC 16).
import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { useLocation } from 'react-router'

import { renderWithProviders } from '../../test/render'
import { http, server } from '../../test/server'
import { Providers } from './providers'
import { AppRoutes } from './routes'

/** Shows the router's current path, so a redirect can be asserted without a page behind it. */
function LocationProbe() {
  const { pathname } = useLocation()
  return <output aria-label="Ruta actual">{pathname}</output>
}

beforeEach(() => {
  server.use(
    http.get('/health', ({ response }) =>
      response(200).json({ status: 'ok', vector: 'available', embedding_model: 'm', store_root: '/s' }),
    ),
  )
})

describe('AppRoutes', () => {
  // spec 002 / AC 16
  it('renders the not-found page inside the layout on an unknown route', async () => {
    renderWithProviders(<AppRoutes />, { route: '/nope' })

    expect(screen.getByRole('heading', { level: 1, name: 'Página no encontrada' })).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Volver a las escenas' })).toHaveAttribute('href', '/scenes')

    const header = screen.getByRole('banner')
    expect(within(header).getByRole('link', { name: 'My Story Marker' })).toHaveAttribute('href', '/scenes')
    const nav = within(header).getByRole('navigation', { name: 'Principal' })
    expect(within(nav).getByRole('link', { name: 'Escenas' })).toHaveAttribute('href', '/scenes')
    expect(within(nav).getByRole('link', { name: 'Grafo 3D' })).toHaveAttribute('href', '/graph3d')
    expect(await within(header).findByText('ok · vector: available')).toBeInTheDocument()
    expect(within(screen.getByRole('main')).getByRole('heading', { level: 1 })).toBeInTheDocument()
  })

  // spec 002 / AC 16
  it('redirects / to /scenes', async () => {
    renderWithProviders(
      <>
        <AppRoutes />
        <LocationProbe />
      </>,
      { route: '/' },
    )
    expect(await screen.findByRole('status', { name: 'Ruta actual' })).toHaveTextContent('/scenes')
    expect(screen.getByRole('banner')).toBeInTheDocument()
    // Let the badge's request settle so it does not outlive the test.
    expect(await screen.findByText('ok · vector: available')).toBeInTheDocument()
  })
})

describe('Providers', () => {
  let broken = true

  function Fragile() {
    if (broken) {
      throw new Error('render failed')
    }
    return <p>contenido</p>
  }

  it('shows the error panel on a render error, and renders again after a retry', async () => {
    // React logs the caught error; it is expected here.
    vi.spyOn(console, 'error').mockImplementation(() => undefined)
    render(
      <Providers>
        <Fragile />
      </Providers>,
    )
    expect(screen.getByRole('alert')).toHaveTextContent('Algo ha fallado al mostrar esta página.')

    broken = false
    await userEvent.click(screen.getByRole('button', { name: 'Reintentar' }))
    expect(screen.getByText('contenido')).toBeInTheDocument()
  })
})
