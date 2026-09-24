// The reader over the typed MSW server (spec 014): the cover shows the dedication from the API,
// and the index marks the chapters changed against the parent version.
import { screen, within } from '@testing-library/react'
import { beforeEach, describe, expect, it } from 'vitest'

import { renderWithProviders } from '../../test/render'
import { http, server } from '../../test/server'
import { AppRoutes } from './routes'

const VERSIONS = [
  { version: 1, status: 'published', parent: null, changed_chapters: [1, 2, 3], note: '', created_at: 't1' },
  { version: 2, status: 'published', parent: 1, changed_chapters: [1, 3], note: '', created_at: 't2' },
]

beforeEach(() => {
  server.use(
    http.get('/health', ({ response }) =>
      response(200).json({ status: 'ok', vector: 'available', embedding_model: 'm', store_root: '/s' }),
    ),
    http.get('/novels/{novel_id}', ({ response }) =>
      response(200).json({
        id: 'demo',
        title: 'La luz de Cabo Luz',
        recipient: 'Lucía',
        dedication: 'Para ti, que siempre vuelves.',
        status: 'published',
        current_version: 2,
        versions: VERSIONS,
      }),
    ),
    http.get('/novels/{novel_id}/versions/{version}/chapters', ({ response }) =>
      response(200).json({
        novel_id: 'demo',
        version: 2,
        status: 'published',
        parent: 1,
        chapters: [
          { n: 1, title: 'La llegada', words: 200, changed_vs_parent: true },
          { n: 2, title: 'El cuaderno', words: 180, changed_vs_parent: false },
          { n: 3, title: 'La luz', words: 190, changed_vs_parent: true },
        ],
      }),
    ),
  )
})

describe('reader (spec 014)', () => {
  // spec 014 / AC 4
  it('shows the cover with the dedication from the API', async () => {
    renderWithProviders(<AppRoutes />, { route: '/novelas/demo' })
    expect(await screen.findByRole('heading', { level: 1, name: 'La luz de Cabo Luz' })).toBeInTheDocument()
    expect(screen.getByText('Para ti, que siempre vuelves.')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Empezar a leer' })).toHaveAttribute('href', '/novelas/demo/capitulos/1?v=2')
  })

  // spec 014 / AC 4
  it('marks the chapters changed against the parent version in the index', async () => {
    renderWithProviders(<AppRoutes />, { route: '/novelas/demo/indice?v=2' })
    const list = await screen.findByRole('list', { name: 'Capítulos' })
    const items = within(list).getAllByRole('listitem')
    expect(items).toHaveLength(3)
    expect(items.map((item) => within(item).queryByText('modificado') !== null)).toEqual([true, false, true])
    expect(screen.getByRole('note')).toHaveTextContent('los capítulos 1, 3')
  })
})
