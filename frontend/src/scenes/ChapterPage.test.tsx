// `/chapters/:id`, the chapter reader, from MSW handlers. Spec 003, FR-READ-01/02/03, AC 15.
import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { HttpResponse } from 'msw'
import { Route, Routes } from 'react-router'
import { describe, expect, it } from 'vitest'

import { renderWithProviders } from '../../test/render'
import { http, server } from '../../test/server'
import type { Schemas } from '../shared/api'
import { ChaptersRoutes, ScenesRoutes } from './routes'

// The two chapter functions of backend/tests/fixtures/repo/structure/chapters.yaml, verbatim.
const SEALED_HALF =
  '"The Sealed Half": every lawful way into the vault is closed to Vance, and the reader learns through Ilan what the co-op takes from the people who go down for it.'
const CALVING_WINDOW =
  '"The Calving Window": the sealing order stops being paper and becomes a clock, and what Vance recovers from the vault she recovers out of her brother rather than out of the co-op.'

function chapter(id: string, fn: string, scenes: string[]): Schemas['Chapter'] {
  return { id, function: fn, arc: 'ar_test', budget: 1000, target_tension_in: 1, target_tension_out: 2, scenes }
}

/** ch01 "The Sealed Half" = 002, 001 (discourse order); ch02 "The Calving Window" = 003; ch03 untitled = 004. */
const BOOK = [
  chapter('ch01', SEALED_HALF, ['002', '001']),
  chapter('ch02', CALVING_WINDOW, ['003']),
  chapter('ch03', 'El cierre, sin título propio.', ['004']),
]

function draft(id: string, body: string): Schemas['Draft'] {
  return { schema_version: 1, scene_ref: id, words: 1100, literal_tail: body, body }
}

const notFound = (detail: string) => HttpResponse.json({ error: 'not_found', detail }, { status: 404 })

/** The chapters and scene ids; a draft for the ids in `bodies`, a 404 for the others. */
function serveBook(bodies: Record<string, string>, chapters: Schemas['Chapter'][] = BOOK) {
  server.use(
    http.get('/structure/chapters', ({ response }) => response(200).json({ schema_version: 1, chapters })),
    http.get('/scenes', ({ response }) => response(200).json(['001', '002', '003', '004'])),
    http.get('/manuscript/{id}', ({ params, response }) => {
      const body = bodies[params.id]
      return body === undefined
        ? response.untyped(notFound(`no draft for ${params.id}`))
        : response(200).json(draft(params.id, body))
    }),
  )
}

function renderReader(route: string) {
  return renderWithProviders(
    <Routes>
      <Route path="/chapters/*" element={<ChaptersRoutes />} />
      <Route path="/scenes/*" element={<ScenesRoutes />} />
    </Routes>,
    { route },
  )
}

function sideIndex(): HTMLElement {
  return screen.getByRole('navigation', { name: 'Índice de capítulos' })
}

function sceneSection(container: HTMLElement, id: string): HTMLElement {
  const section = container.querySelector<HTMLElement>(`section#scene-${id}`)
  if (section === null) {
    throw new Error(`no section for scene ${id}`)
  }
  return section
}

describe('ChapterPage', () => {
  // spec 003 / AC 15
  it('shows a skeleton while the chapters load, then the chapter titled from its function', async () => {
    serveBook({ '002': 'Dos.' })
    renderReader('/chapters/ch01')
    expect(screen.getByRole('status')).toHaveTextContent('Cargando…')
    expect(await screen.findByRole('heading', { level: 1, name: 'The Sealed Half' })).toBeInTheDocument()
    expect(screen.getAllByRole('heading', { level: 1 })).toHaveLength(1)
    expect(screen.getByText('Capítulo 1')).toHaveClass('eyebrow')
    expect(
      screen.getByText(
        'Every lawful way into the vault is closed to Vance, and the reader learns through Ilan what the co-op takes from the people who go down for it.',
      ),
    ).toBeInTheDocument()
    expect(screen.getByText('2 escenas')).toBeInTheDocument()
    await waitFor(() => {
      expect(document.title).toBe('Capítulo 1 · The Sealed Half · My Story Marker')
    })
  })

  // spec 003 / AC 15
  it('lists every chapter in the side index, the current one marked, with its scenes as anchors', async () => {
    serveBook({})
    renderReader('/chapters/ch01')
    await screen.findByRole('heading', { level: 1, name: 'The Sealed Half' })
    const nav = sideIndex()
    const first = within(nav).getByRole('link', { name: '1 · The Sealed Half' })
    const second = within(nav).getByRole('link', { name: '2 · The Calving Window' })
    const third = within(nav).getByRole('link', { name: 'Capítulo 3' })
    expect(first).toHaveAttribute('aria-current', 'page')
    expect(first).toHaveAttribute('href', '/chapters/ch01')
    expect(second).not.toHaveAttribute('aria-current')
    expect(second).toHaveAttribute('href', '/chapters/ch02')
    expect(third).toHaveAttribute('href', '/chapters/ch03')
    expect(within(nav).getAllByRole('link', { current: 'page' })).toEqual([first])
    // Only the current chapter's scenes, in its order, as in-page anchors.
    const anchors = within(nav).getAllByRole('link', { name: /^Escena / })
    expect(anchors.map((a) => [a.textContent, a.getAttribute('href')])).toEqual([
      ['Escena 002', '#scene-002'],
      ['Escena 001', '#scene-001'],
    ])
    expect(within(nav).getByRole('link', { name: 'Ver el índice completo' })).toHaveAttribute('href', '/scenes')
  })

  // spec 003 / AC 15
  it("shows each scene's prose in order under its anchor, and the empty note without a draft", async () => {
    serveBook({ '002': 'Primer párrafo con *énfasis*.\n\nSegundo párrafo.' })
    const { container } = renderReader('/chapters/ch01')
    expect(await screen.findByText('Esta escena aún no tiene borrador')).toBeInTheDocument()
    expect(await screen.findByText('énfasis')).toBeInTheDocument()

    const sections = [...container.querySelectorAll('section.chapter-scene')]
    expect(sections.map((section) => section.id)).toEqual(['scene-002', 'scene-001'])

    const withDraft = sceneSection(container, '002')
    expect(within(withDraft).getByRole('heading', { level: 2, name: 'Escena 002' })).toBeInTheDocument()
    expect(within(withDraft).getByRole('link', { name: 'Escena 002' })).toHaveAttribute('href', '/scenes/002')
    expect(screen.getByRole('region', { name: 'Escena 002' })).toBe(withDraft)
    expect(withDraft.querySelector('.prose em')).toHaveTextContent('énfasis')
    expect(withDraft.querySelectorAll('.prose p')).toHaveLength(2)
    expect(within(withDraft).queryByText('Esta escena aún no tiene borrador')).not.toBeInTheDocument()

    const withoutDraft = sceneSection(container, '001')
    expect(within(withoutDraft).getByText('Esta escena aún no tiene borrador')).toBeInTheDocument()
    expect(withoutDraft.querySelector('.prose')).toBeNull()
    expect(screen.getByText('1100 palabras')).toBeInTheDocument()
    expect(screen.queryByRole('alert')).not.toBeInTheDocument()
  })

  // spec 003 / AC 15 (FR-READ-03)
  it('shows an error line in the scene whose draft fails, and the rest of the chapter', async () => {
    serveBook({ '002': 'Dos sigue aquí.' })
    server.use(
      http.get('/manuscript/{id}', ({ params, response }) =>
        params.id === '001'
          ? response.untyped(HttpResponse.json({ error: 'invalid_record', detail: 'borrador corrupto' }, { status: 422 }))
          : response(200).json(draft(params.id, 'Dos sigue aquí.')),
      ),
    )
    const { container } = renderReader('/chapters/ch01')
    await screen.findByRole('article')
    const failing = sceneSection(container, '001')
    expect(await within(failing).findByText(/borrador corrupto/)).toBeInTheDocument()
    expect(within(failing).getByRole('button', { name: 'Reintentar' })).toBeInTheDocument()
    expect(within(sceneSection(container, '002')).getByText('Dos sigue aquí.')).toBeInTheDocument()
    expect(screen.queryByRole('alert')).not.toBeInTheDocument()
  })

  // spec 003 / AC 15 (FR-READ-02)
  it('offers previous and next chapters only where they exist, and following them opens them', async () => {
    serveBook({ '002': 'Dos.', '003': 'Tres.', '004': 'Cuatro.' })
    renderReader('/chapters/ch01')
    await screen.findByRole('heading', { level: 1, name: 'The Sealed Half' })
    let nav = screen.getByRole('navigation', { name: 'Capítulos vecinos' })
    expect(within(nav).queryByRole('link', { name: /^Capítulo anterior/ })).not.toBeInTheDocument()
    const next = within(nav).getByRole('link', { name: 'Capítulo siguiente: The Calving Window' })
    expect(next).toHaveAttribute('href', '/chapters/ch02')
    expect(next).toHaveClass('scenes-cta')

    await userEvent.click(next)
    expect(await screen.findByRole('heading', { level: 1, name: 'The Calving Window' })).toBeInTheDocument()
    expect(await screen.findByText('Tres.')).toBeInTheDocument()
    nav = screen.getByRole('navigation', { name: 'Capítulos vecinos' })
    expect(within(nav).getByRole('link', { name: 'Capítulo anterior: The Sealed Half' })).toHaveAttribute(
      'href',
      '/chapters/ch01',
    )
    const last = within(nav).getByRole('link', { name: 'Capítulo siguiente: Capítulo 3' })
    expect(within(sideIndex()).getByRole('link', { current: 'page' })).toHaveAccessibleName('2 · The Calving Window')

    await userEvent.click(last)
    expect(await screen.findByRole('heading', { level: 1, name: 'Capítulo 3' })).toBeInTheDocument()
    expect(await screen.findByText('Cuatro.')).toBeInTheDocument()
    nav = screen.getByRole('navigation', { name: 'Capítulos vecinos' })
    expect(within(nav).getByRole('link', { name: 'Capítulo anterior: The Calving Window' })).toBeInTheDocument()
    expect(within(nav).queryByRole('link', { name: /^Capítulo siguiente/ })).not.toBeInTheDocument()
    // An untitled chapter has no eyebrow repeating its heading.
    expect(screen.getAllByText('Capítulo 3')).toHaveLength(2) // the heading and the side-index link
  })

  // spec 003 / AC 15 (FR-READ-03)
  it.each([
    ['an unknown chapter id', () => {
      serveBook({})
    }],
    ['a book without a chapter structure (404)', () => {
      server.use(
        http.get('/structure/chapters', ({ response }) => response.untyped(notFound('no chapters'))),
        http.get('/scenes', ({ response }) => response(200).json(['001'])),
      )
    }],
  ])('shows not-found, without a retry, for %s', async (_case, serve) => {
    serve()
    const requests: string[] = []
    const record = ({ request }: { request: Request }) => {
      requests.push(new URL(request.url).pathname)
    }
    server.events.on('request:start', record)
    try {
      renderReader('/chapters/ch99')
      expect(await screen.findByRole('heading', { level: 1, name: 'Capítulo no encontrado' })).toBeInTheDocument()
      expect(screen.getByRole('link', { name: 'Volver al índice' })).toHaveAttribute('href', '/scenes')
      expect(screen.queryByRole('button', { name: 'Reintentar' })).not.toBeInTheDocument()
      expect(requests.filter((path) => path.includes('/manuscript/'))).toEqual([])
    } finally {
      server.events.removeListener('request:start', record)
    }
  })

  // spec 003 / AC 15 (FR-READ-03)
  it('shows the error panel when the chapters fail, and retrying recovers', async () => {
    serveBook({ '002': 'Recuperado.' })
    let calls = 0
    server.use(
      http.get('/structure/chapters', ({ response }) => {
        calls += 1
        return calls === 1
          ? response.untyped(
              HttpResponse.json({ error: 'store_unreadable', detail: 'chapters.yaml ilegible' }, { status: 500 }),
            )
          : response(200).json({ schema_version: 1, chapters: BOOK })
      }),
    )
    renderReader('/chapters/ch01')
    const alert = await screen.findByRole('alert')
    expect(alert).toHaveTextContent('chapters.yaml ilegible')
    expect(screen.queryByRole('navigation', { name: 'Índice de capítulos' })).not.toBeInTheDocument()
    await userEvent.click(within(alert).getByRole('button', { name: 'Reintentar' }))
    expect(await screen.findByText('Recuperado.')).toBeInTheDocument()
    expect(screen.queryByRole('alert')).not.toBeInTheDocument()
  })

  // spec 003 / AC 15
  it('says so when the chapter has no scenes', async () => {
    serveBook({}, [chapter('ch01', SEALED_HALF, [])])
    renderReader('/chapters/ch01')
    expect(await screen.findByText('Este capítulo todavía no tiene escenas')).toBeInTheDocument()
    expect(screen.getByText('0 escenas')).toBeInTheDocument()
    expect(screen.queryByRole('navigation', { name: 'Capítulos vecinos' })).not.toBeInTheDocument()
  })

  // spec 003 / AC 15 (FR-BIBLE-03 links land on /chapters/:id#scene-NNN)
  it('brings the scene named in the address into view once the drafts have settled', async () => {
    const scrolled: string[] = []
    Object.defineProperty(Element.prototype, 'scrollIntoView', {
      configurable: true,
      value: function scrollIntoView(this: Element) {
        scrolled.push(this.id)
      },
    })
    try {
      serveBook({ '002': 'Dos.' })
      renderReader('/chapters/ch01#scene-001')
      expect(await screen.findByText('Esta escena aún no tiene borrador')).toBeInTheDocument()
      await waitFor(() => {
        expect(scrolled).toEqual(['scene-001'])
      })
    } finally {
      Reflect.deleteProperty(Element.prototype, 'scrollIntoView')
    }
  })

  it('sends /chapters on its own to the index', async () => {
    serveBook({})
    renderReader('/chapters')
    expect(await screen.findByRole('heading', { level: 1, name: 'Índice' })).toBeInTheDocument()
  })
})
