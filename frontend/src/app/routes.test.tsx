// app/'s route table and providers. Spec 002, FR-SHELL-01 and FR-SHELL-03 (AC 16); spec 003,
// FR-IA (revision 2); spec 014: `/` lists the novels, navigation Novelas · Nueva novela · Cómo funciona (Escenas removed).
import { render, screen, waitFor, within } from '@testing-library/react'
import { HttpResponse } from 'msw'
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
    // The pages behind the routes these tests visit load these; the tests only look at the shell.
    http.get('/cast', ({ response }) => response(200).json([])),
    http.get('/canon/locations', ({ response }) => response(200).json({ kind: 'locations', ids: [] })),
    http.get('/cast/{id}', ({ response }) =>
      response.untyped(HttpResponse.json({ error: 'not_found', detail: 'no such character' }, { status: 404 })),
    ),
    // Spec 014: the novels list at `/` and a novel's reader.
    http.get('/novels', ({ response }) => response(200).json([])),
    http.get('/novels/{novel_id}', ({ response }) =>
      response(200).json({ id: 'demo', title: 'Demo', status: 'draft', current_version: null, versions: [] }),
    ),
    // The legacy cover loaded the premise.
    http.get('/canon/project', ({ response }) =>
      response(200).json({
        schema_version: 1,
        premise: { statement: 'Premisa', dramatic_question: '¿Pregunta?', answer: 'Respuesta' },
        thesis: { proposition: 'Tesis', antithesis: 'Antítesis' },
        genre_contract: { subgenre: 'sf', rigour: 'rigor', limits: 'límites' },
        body: '',
      }),
    ),
  )
})

describe('AppRoutes', () => {
  // spec 002 / AC 16
  it('renders the not-found page inside the layout on an unknown route', async () => {
    renderWithProviders(<AppRoutes />, { route: '/nope' })

    expect(screen.getByRole('heading', { level: 1, name: 'Página no encontrada' })).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Volver a la biblioteca' })).toHaveAttribute('href', '/')

    const header = screen.getByRole('banner')
    // Revised by spec 003 (revision 2): the brand leads to the cover; the navigation is new.
    expect(within(header).getByRole('link', { name: 'My Story Marker' })).toHaveAttribute('href', '/')
    const nav = within(header).getByRole('navigation', { name: 'Principal' })
    // Revised by spec 014: the reader's own navigation lives inside each novel.
    expect(within(nav).getByRole('link', { name: 'Novelas' })).toHaveAttribute('href', '/')
    expect(within(nav).queryByRole('link', { name: 'Escenas' })).toBeNull()
    expect(await within(header).findByText('ok · vector: available')).toBeInTheDocument()
    expect(within(screen.getByRole('main')).getByRole('heading', { level: 1 })).toBeInTheDocument()
  })

  // spec 002 / AC 16, revised by spec 003 (revision 2) and spec 014: `/` lists the novels.
  it('shows the novels at /', async () => {
    renderWithProviders(
      <>
        <AppRoutes />
        <LocationProbe />
      </>,
      { route: '/' },
    )
    expect(await screen.findByRole('status', { name: 'Ruta actual' })).toHaveTextContent(/^\/$/)
    expect(screen.getByRole('banner')).toBeInTheDocument()
    expect(within(screen.getByRole('main')).getByRole('heading', { level: 1 })).toBeInTheDocument()
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

describe('Layout (spec 003)', () => {
  // spec 003 / AC 6
  it('keeps the brand name exactly "My Story Marker" with the logo inside the link', () => {
    renderWithProviders(<AppRoutes />, { route: '/nope' })
    const brand = within(screen.getByRole('banner')).getByRole('link', { name: 'My Story Marker' })
    expect(brand.querySelector('img')).not.toBeNull()
  })

  // spec 003 / AC 6
  it.each([
    ['/', 'Novelas'],
    ['/novelas/demo', 'Novelas'],
    ['/arquitectura', 'Cómo funciona'],
  ])('on %s marks only "%s" with aria-current="page"', async (route, current) => {
    renderWithProviders(<AppRoutes />, { route })
    const nav = within(screen.getByRole('banner')).getByRole('navigation', { name: 'Principal' })
    await waitFor(() => {
      expect(within(nav).getByRole('link', { name: current })).toHaveAttribute('aria-current', 'page')
    })
    const marked = within(nav)
      .getAllByRole('link')
      .filter((link) => link.getAttribute('aria-current') === 'page')
    expect(marked).toHaveLength(1)
  })

  // spec 003 / AC 6
  it('has a footer landmark', () => {
    renderWithProviders(<AppRoutes />, { route: '/nope' })
    const footer = screen.getByRole('contentinfo')
    expect(footer).toHaveTextContent('My Story Marker')
    expect(within(footer).getByRole('link', { name: 'Vista 3D' })).toHaveAttribute('href', '/graph3d')
  })
})
