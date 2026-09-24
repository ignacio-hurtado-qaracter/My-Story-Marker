// The book header of `/scenes`, from MSW handlers. Spec 003, FR-BOOK-01/02/03, AC 5.
import { screen, waitFor, within } from '@testing-library/react'
import { HttpResponse } from 'msw'
import { Route, Routes } from 'react-router'
import { afterEach, describe, expect, it } from 'vitest'

import { renderWithProviders } from '../../test/render'
import { http, server } from '../../test/server'
import type { Schemas } from '../shared/api'
import { ScenesRoutes } from './routes'

const STATEMENT = 'Una cartógrafa quiere volver a casa, pero su nave ya no recuerda la ruta.'
const QUESTION = '¿Llegará antes de que la nave la olvide también a ella?'
const ANSWER = 'Llega, pero ya no es la misma persona que partió.'

const PROJECT: Schemas['Project'] = {
  schema_version: 1,
  premise: { statement: STATEMENT, dramatic_question: QUESTION, answer: ANSWER },
  thesis: { proposition: 'La memoria es un lugar', antithesis: 'La memoria es solo ruido', test_scenes: ['002'] },
  genre_contract: {
    subgenre: 'sf_test',
    rigour: 'Rigor de prueba',
    limits: 'Límites de prueba',
    promises: [{ promise: 'Promesa de prueba', payoff_scene: null }],
  },
  body: 'Cuerpo de prueba',
}

/** ch01 = 001, 002; ch02 = 003; 004 belongs to no chapter: 2 chapters, 4 scenes. */
const CHAPTERS: Schemas['Chapter'][] = [
  { id: 'ch01', function: 'f1', arc: 'a', budget: 1, target_tension_in: 1, target_tension_out: 2, scenes: ['001', '002'] },
  { id: 'ch02', function: 'f2', arc: 'a', budget: 1, target_tension_in: 2, target_tension_out: 3, scenes: ['003'] },
]
const SCENE_IDS = ['001', '002', '003', '004']

/** A request the test holds open until it calls `open()`. */
interface Gate {
  wait: Promise<void>
  open: () => void
}

const gates: Gate[] = []

function gate(): Gate {
  let open: () => void = () => undefined
  const wait = new Promise<void>((resolve) => {
    open = () => {
      resolve()
    }
  })
  const created = { wait, open }
  gates.push(created)
  return created
}

// No request is left hanging into the next test.
afterEach(() => {
  for (const g of gates.splice(0)) {
    g.open()
  }
})

function serveToc(held?: Gate) {
  server.use(
    http.get('/structure/chapters', async ({ response }) => {
      await held?.wait
      return response(200).json({ schema_version: 1, chapters: CHAPTERS })
    }),
    http.get('/scenes', ({ response }) => response(200).json(SCENE_IDS)),
  )
}

function serveProject(held?: Gate) {
  server.use(
    http.get('/canon/project', async ({ response }) => {
      await held?.wait
      return response(200).json(PROJECT)
    }),
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

function bookHeader(): HTMLElement {
  const section = screen.getByRole('heading', { level: 1, name: 'Escenas' }).closest('section')
  if (section === null) {
    throw new Error('no section around the page title')
  }
  return section
}

const COUNT_PILL = /^\d+ (capítulos?|escenas?)$/

describe('BookHeader', () => {
  // spec 003 / AC 5
  it('shows the premise statement and dramatic question, and never the answer', async () => {
    serveToc()
    serveProject()
    const { container } = renderToc()
    expect(await screen.findByText(STATEMENT)).toBeInTheDocument()
    const header = bookHeader()
    expect(within(header).getByText(STATEMENT)).toBeInTheDocument()
    expect(within(header).getByText(QUESTION)).toBeInTheDocument()
    expect(within(header).getByText('Novela')).toBeInTheDocument()
    // FR-BOOK-01: a section, never a <header>; the page keeps a single h1 and no h2 up here.
    expect(container.querySelector('header')).toBeNull()
    expect(screen.getAllByRole('heading', { level: 1 })).toHaveLength(1)
    expect(within(header).queryByRole('heading', { level: 2 })).not.toBeInTheDocument()
    expect(within(header).queryByRole('link')).not.toBeInTheDocument()
    // The answer is a spoiler: it is in the response, never on the page.
    await screen.findByRole('link', { name: 'Escena 001' })
    expect(document.body).not.toHaveTextContent(ANSWER)
    expect(screen.queryByText(ANSWER, { exact: false })).not.toBeInTheDocument()
  })

  // spec 003 / AC 5
  it('shows no premise while it loads, and no second status', async () => {
    const toc = gate()
    const project = gate()
    serveToc(toc)
    serveProject(project)
    const { container } = renderToc()

    // Both pending: the table of contents' skeleton is the only status.
    expect(screen.getAllByRole('status')).toHaveLength(1)
    expect(screen.getByRole('status')).toHaveTextContent('Cargando…')
    expect(screen.queryByText(STATEMENT)).not.toBeInTheDocument()
    const placeholder = container.querySelector('.book-premise-skeleton')
    expect(placeholder).toHaveAttribute('aria-hidden', 'true')
    expect(placeholder).toHaveTextContent('')

    // The chapters arrive first: no status at all, and still no premise.
    toc.open()
    expect(await screen.findByRole('link', { name: 'Escena 001' })).toBeInTheDocument()
    expect(screen.queryAllByRole('status')).toHaveLength(0)
    expect(screen.queryByText(STATEMENT)).not.toBeInTheDocument()
    expect(screen.queryByText('Pregunta dramática')).not.toBeInTheDocument()

    project.open()
    expect(await screen.findByText(STATEMENT)).toBeInTheDocument()
    expect(container.querySelector('.book-premise-skeleton')).toBeNull()
    expect(screen.queryAllByRole('status')).toHaveLength(0)
  })

  // spec 003 / AC 5
  it.each([
    [500, 'store_unreadable'],
    [404, 'not_found'],
  ])('omits the premise on a %i while the chapters still render', async (status, code) => {
    serveToc()
    server.use(
      http.get('/canon/project', ({ response }) =>
        response.untyped(HttpResponse.json({ error: code, detail: 'project.md ilegible' }, { status })),
      ),
    )
    const { container } = renderToc()
    expect(await screen.findByRole('heading', { level: 2, name: 'ch01' })).toBeInTheDocument()
    await waitFor(() => {
      expect(container.querySelector('.book-premise-skeleton')).toBeNull()
    })
    expect(screen.getAllByRole('heading', { level: 2 }).map((h) => h.textContent)).toEqual(['ch01', 'ch02', 'Sin capítulo'])
    expect(screen.getByRole('heading', { level: 1, name: 'Escenas' })).toBeInTheDocument()
    expect(container.querySelector('.book-premise')).toBeNull()
    expect(screen.queryByText('Pregunta dramática')).not.toBeInTheDocument()
    expect(screen.queryByText('project.md ilegible')).not.toBeInTheDocument()
    expect(screen.queryByRole('alert')).not.toBeInTheDocument()
  })

  // spec 003 / AC 5
  it('shows the count pills only once the table of contents has loaded', async () => {
    const toc = gate()
    serveToc(toc)
    serveProject()
    renderToc()
    // The premise is there, the table of contents is not: no pills yet.
    expect(await screen.findByText(STATEMENT)).toBeInTheDocument()
    expect(screen.getByRole('status')).toHaveTextContent('Cargando…')
    expect(screen.queryByText(COUNT_PILL)).not.toBeInTheDocument()

    toc.open()
    const header = bookHeader()
    expect(await within(header).findByText('2 capítulos')).toBeInTheDocument()
    expect(within(header).getByText('4 escenas')).toBeInTheDocument()
  })

  // spec 003 / AC 5
  it('shows no count pills when the table of contents fails', async () => {
    server.use(
      http.get('/structure/chapters', ({ response }) =>
        response.untyped(HttpResponse.json({ error: 'store_unreadable', detail: 'chapters.yaml ilegible' }, { status: 500 })),
      ),
      http.get('/scenes', ({ response }) => response(200).json(SCENE_IDS)),
    )
    serveProject()
    renderToc()
    expect(await screen.findByRole('alert')).toHaveTextContent('chapters.yaml ilegible')
    expect(await screen.findByText(STATEMENT)).toBeInTheDocument()
    expect(screen.queryByText(COUNT_PILL)).not.toBeInTheDocument()
  })
})
