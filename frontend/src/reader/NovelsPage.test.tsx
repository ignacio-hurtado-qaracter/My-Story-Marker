// The library at `/` (spec 019) over the typed MSW server: one card per novel with its status,
// version, chapter count and links; the chips filter published novels from the others.
import { screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it } from 'vitest'

import { renderWithProviders } from '../../test/render'
import { http, server } from '../../test/server'
import { NovelsPage } from './NovelsPage'

const V = (version: number, status: string) => ({
  version,
  status,
  parent: version > 1 ? version - 1 : null,
  changed_chapters: [],
  note: '',
  created_at: 't',
})

beforeEach(() => {
  server.use(
    http.get('/novels', ({ response }) =>
      response(200).json([
        { id: 'faro', title: 'La luz de Cabo Luz', recipient: 'Lucía', status: 'published', current_version: 2 },
        { id: 'roto', title: 'El mapa roto', recipient: 'Pablo', status: 'stopped_error', current_version: null },
      ]),
    ),
    http.get('/novels/{novel_id}', ({ params, response }) =>
      params.novel_id === 'faro'
        ? response(200).json({
            id: 'faro',
            title: 'La luz de Cabo Luz',
            recipient: 'Lucía',
            status: 'published',
            current_version: 2,
            versions: [V(1, 'published'), V(2, 'published')],
          })
        : response(200).json({
            id: 'roto',
            title: 'El mapa roto',
            recipient: 'Pablo',
            status: 'stopped_error',
            current_version: null,
            versions: [V(1, 'blocked')],
          }),
    ),
    http.get('/novels/{novel_id}/versions/{version}/chapters', ({ response }) =>
      response(200).json({
        novel_id: 'faro',
        version: 2,
        status: 'published',
        parent: 1,
        chapters: [1, 2, 3].map((n) => ({ n, title: `Capítulo ${String(n)}`, words: 1200, changed_vs_parent: false })),
      }),
    ),
  )
})

describe('NovelsPage (spec 019)', () => {
  // spec 019 / AC 4
  it('renders a card per novel with status, version, chapters and links', async () => {
    renderWithProviders(<NovelsPage />)
    expect(screen.getByRole('heading', { level: 1, name: 'Biblioteca' })).toBeInTheDocument()
    const list = await screen.findByRole('list', { name: 'Novelas' })
    const [faro, roto] = await within(list).findAllByRole('listitem')
    if (faro === undefined || roto === undefined) throw new Error('expected two cards')

    expect(within(faro).getByRole('heading', { level: 2, name: 'La luz de Cabo Luz' })).toBeInTheDocument()
    expect(within(faro).getByText('Para Lucía')).toBeInTheDocument()
    expect(within(faro).getByText('Publicada')).toBeInTheDocument()
    expect(within(faro).getByText('Versión 2')).toBeInTheDocument()
    expect(await within(faro).findByText(/3 capítulos/)).toBeInTheDocument()
    expect(within(faro).getByRole('link', { name: 'Índice' })).toHaveAttribute('href', '/novelas/faro/indice?v=2')
    expect(within(faro).getByRole('link', { name: 'PDF' })).toHaveAttribute('href', '/api/novels/faro/versions/2/pdf')

    expect(await within(roto).findByText('Bloqueada')).toBeInTheDocument()
    expect(within(roto).queryByRole('link', { name: 'PDF' })).toBeNull()
  })

  // spec 019 / AC 4
  it('filters published novels from the others', async () => {
    const user = userEvent.setup()
    renderWithProviders(<NovelsPage />)
    const list = await screen.findByRole('list', { name: 'Novelas' })
    expect(await within(list).findAllByRole('listitem')).toHaveLength(2)

    await user.click(screen.getByRole('button', { name: /^Publicadas/ }))
    expect(within(list).getAllByRole('listitem')).toHaveLength(1)
    expect(within(list).getByText('La luz de Cabo Luz')).toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: /^Otras/ }))
    expect(within(list).getAllByRole('listitem')).toHaveLength(1)
    expect(within(list).getByText('El mapa roto')).toBeInTheDocument()
  })
})
