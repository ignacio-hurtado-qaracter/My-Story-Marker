// `/scenes` in its four states, from MSW handlers. Spec 002, FR-SCN route table, AC 8.
// Spec 003, FR-INDEX (revision 2): the chapter index, AC 14. Spec 002's chapter headings now
// carry the display title before the chapter id, and each card adds a "Leer capítulo" link;
// plan 003 Q14 lists the assertions adjusted for that.
import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { HttpResponse } from 'msw'
import { Route, Routes } from 'react-router'
import { describe, expect, it } from 'vitest'

import { renderWithProviders } from '../../test/render'
import { http, server } from '../../test/server'
import type { Schemas } from '../shared/api'
import { ScenesRoutes } from './routes'

function chapter(id: string, scenes: string[]): Schemas['Chapter'] {
  return {
    id,
    function: `Función dramática de ${id}`,
    arc: 'ar_test',
    budget: 1000,
    target_tension_in: 1,
    target_tension_out: 2,
    scenes,
  }
}

// The two chapter functions of backend/tests/fixtures/repo/structure/chapters.yaml, verbatim.
const SEALED_HALF =
  '"The Sealed Half": every lawful way into the vault is closed to Vance, and the reader learns through Ilan what the co-op takes from the people who go down for it.'
const CALVING_WINDOW =
  '"The Calving Window": the sealing order stops being paper and becomes a clock, and what Vance recovers from the vault she recovers out of her brother rather than out of the co-op.'

function titled(id: string, fn: string, scenes: string[]): Schemas['Chapter'] {
  return { ...chapter(id, scenes), function: fn }
}

// spec 003 (revision 2): the book header moved to the cover, so `/scenes` no longer reads the
// project record (plan 003 Q10).
function serveToc(chapters: Schemas['Chapter'][], ids: string[]) {
  server.use(
    http.get('/structure/chapters', ({ response }) => response(200).json({ schema_version: 1, chapters })),
    http.get('/scenes', ({ response }) => response(200).json(ids)),
  )
}

function renderToc() {
  return renderWithProviders(
    <Routes>
      <Route path="/scenes/*" element={<ScenesRoutes />} />
    </Routes>,
    { route: '/scenes' },
  )
}

function linkNames(element: HTMLElement): string[] {
  return within(element)
    .getAllByRole('link')
    .map((link) => link.textContent)
}

function sectionOf(headingName: string | ((name: string) => boolean)): HTMLElement {
  const section = screen.getByRole('heading', { level: 2, name: headingName }).closest('section')
  if (section === null) {
    throw new Error('no section for that heading')
  }
  return section
}

/** A chapter's card, by the chapter id that ends its heading (spec 003: title, then id). */
function chapterSection(id: string): HTMLElement {
  return sectionOf((name) => name.endsWith(` ${id}`))
}

describe('TocPage', () => {
  // spec 002 / AC 8
  it('shows a skeleton while loading', async () => {
    serveToc([chapter('ch01', ['001'])], ['001'])
    renderToc()
    expect(screen.getByRole('status')).toHaveTextContent('Cargando…')
    expect(await screen.findByRole('link', { name: 'Escena 001' })).toBeInTheDocument()
  })

  // spec 002 / AC 8
  it('shows the empty state when there are no chapters and no scenes', async () => {
    serveToc([], [])
    renderToc()
    expect(await screen.findByText('Todavía no hay escenas')).toBeInTheDocument()
  })

  it('treats a missing chapter structure (404) as no chapters', async () => {
    server.use(
      http.get('/structure/chapters', ({ response }) =>
        response.untyped(HttpResponse.json({ error: 'not_found', detail: 'no chapters' }, { status: 404 })),
      ),
      http.get('/scenes', ({ response }) => response(200).json([])),
    )
    renderToc()
    expect(await screen.findByText('Todavía no hay escenas')).toBeInTheDocument()
  })

  // spec 002 / AC 8
  it('shows the IF-07 detail of an error, and retrying recovers', async () => {
    let calls = 0
    server.use(
      http.get('/structure/chapters', ({ response }) => {
        calls += 1
        return calls === 1
          ? response.untyped(
              HttpResponse.json({ error: 'store_unreadable', detail: 'chapters.yaml ilegible' }, { status: 500 }),
            )
          : response(200).json({ schema_version: 1, chapters: [chapter('ch01', ['001'])] })
      }),
      http.get('/scenes', ({ response }) => response(200).json(['001'])),
    )
    renderToc()
    const alert = await screen.findByRole('alert')
    expect(alert).toHaveTextContent('chapters.yaml ilegible')
    await userEvent.click(within(alert).getByRole('button', { name: 'Reintentar' }))
    expect(await screen.findByRole('link', { name: 'Escena 001' })).toBeInTheDocument()
    expect(screen.queryByRole('alert')).not.toBeInTheDocument()
  })

  // spec 002 / AC 8
  it('lists chapters in file order with their function, each in its own scene order', async () => {
    serveToc([chapter('ch01', ['003', '001']), chapter('ch02', ['002'])], ['001', '002', '003'])
    renderToc()
    await screen.findByRole('link', { name: 'Escena 003' })
    // spec 003 / AC 14: an untitled chapter's heading is "Capítulo N", then its id.
    expect(screen.getAllByRole('heading', { level: 2 }).map((h) => h.textContent)).toEqual([
      'Capítulo 1 ch01',
      'Capítulo 2 ch02',
    ])
    expect(chapterSection('ch01')).toHaveTextContent('Función dramática de ch01')
    expect(linkNames(chapterSection('ch01'))).toEqual(['Escena 003', 'Escena 001', 'Leer capítulo'])
    expect(linkNames(chapterSection('ch02'))).toEqual(['Escena 002', 'Leer capítulo'])
    expect(screen.getByRole('link', { name: 'Escena 003' })).toHaveAttribute('href', '/scenes/003')
    expect(screen.queryByRole('heading', { name: 'Sin capítulo' })).not.toBeInTheDocument()
  })

  // spec 002 / AC 8
  it('lists a scene no chapter names last, under "Sin capítulo"', async () => {
    serveToc([chapter('ch01', ['002'])], ['004', '002'])
    renderToc()
    await screen.findByRole('link', { name: 'Escena 004' })
    expect(screen.getAllByRole('heading', { level: 2 }).map((h) => h.textContent)).toEqual([
      'Capítulo 1 ch01',
      'Sin capítulo',
    ])
    expect(linkNames(sectionOf('Sin capítulo'))).toEqual(['Escena 004'])
    expect(screen.getAllByRole('link').map((link) => link.textContent)).toEqual([
      'Escena 002',
      'Leer capítulo',
      'Escena 004',
    ])
  })

  // spec 003 / AC 14
  it('is titled "Índice", with the count pills once loaded', async () => {
    serveToc([chapter('ch01', ['001', '002']), chapter('ch02', ['003'])], ['001', '002', '003', '004'])
    renderToc()
    expect(screen.getByRole('heading', { level: 1, name: 'Índice' })).toBeInTheDocument()
    expect(screen.queryByText('2 capítulos')).not.toBeInTheDocument()
    expect(await screen.findByText('2 capítulos')).toBeInTheDocument()
    expect(screen.getByText('4 escenas')).toBeInTheDocument()
    expect(screen.getAllByRole('heading', { level: 1 })).toHaveLength(1)
    await waitFor(() => {
      expect(document.title).toBe('Índice · My Story Marker')
    })
  })

  // spec 003 / AC 14
  it('numbers the chapters in file order and titles them from their function', async () => {
    serveToc(
      [
        titled('ch01', SEALED_HALF, ['001', '002', '003']),
        titled('ch02', CALVING_WINDOW, ['004']),
        chapter('ch03', ['005']),
      ],
      ['001', '002', '003', '004', '005'],
    )
    renderToc()
    await screen.findByRole('link', { name: 'Escena 005' })
    expect(screen.getAllByRole('heading', { level: 2 }).map((h) => h.textContent)).toEqual([
      'The Sealed Half ch01',
      'The Calving Window ch02',
      'Capítulo 3 ch03',
    ])
    const first = chapterSection('ch01')
    expect(within(first).getByText('Capítulo 1')).toHaveClass('eyebrow')
    expect(first).toHaveTextContent(
      'Every lawful way into the vault is closed to Vance, and the reader learns through Ilan what the co-op takes from the people who go down for it.',
    )
    expect(first).not.toHaveTextContent('"The Sealed Half"')
    expect(within(first).getByText('3 escenas')).toBeInTheDocument()
    expect(within(chapterSection('ch02')).getByText('Capítulo 2')).toHaveClass('eyebrow')
    expect(within(chapterSection('ch02')).getByText('1 escena')).toBeInTheDocument()
    // An untitled chapter says "Capítulo 3" once, in its heading, not again as an eyebrow.
    expect(within(chapterSection('ch03')).getAllByText('Capítulo 3')).toHaveLength(1)
  })

  // spec 003 / AC 14
  it('links each chapter to its reader, and the unlisted scenes to no reader', async () => {
    serveToc([titled('ch01', SEALED_HALF, ['001']), titled('ch02', CALVING_WINDOW, ['002'])], ['001', '002', '009'])
    renderToc()
    await screen.findByRole('link', { name: 'Escena 009' })
    const read = screen.getAllByRole('link', { name: 'Leer capítulo' })
    expect(read.map((link) => link.getAttribute('href'))).toEqual(['/chapters/ch01', '/chapters/ch02'])
    expect(within(chapterSection('ch01')).getByRole('link', { name: 'Leer capítulo' })).toHaveAttribute(
      'href',
      '/chapters/ch01',
    )
    expect(within(sectionOf('Sin capítulo')).queryByRole('link', { name: 'Leer capítulo' })).not.toBeInTheDocument()
    expect(within(sectionOf('Sin capítulo')).getByRole('link', { name: 'Escena 009' })).toHaveAttribute(
      'href',
      '/scenes/009',
    )
  })
})
