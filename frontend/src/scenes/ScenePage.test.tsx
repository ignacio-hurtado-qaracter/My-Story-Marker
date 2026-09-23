// `/scenes/:id` in its states, from MSW handlers. Spec 002, FR-SCN route table, FR-SCN-02,
// FR-SCN-03, FR-SCN-06, FR-TOOL-05, AC 9.
import { screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { HttpResponse } from 'msw'
import { Route, Routes } from 'react-router'
import { describe, expect, it } from 'vitest'

import { renderWithProviders } from '../../test/render'
import { http, server } from '../../test/server'
import type { Schemas } from '../shared/api'
import { ScenesRoutes } from './routes'

function scene(id: string): Schemas['Scene'] {
  return {
    schema_version: 1,
    id,
    pov: 'pov_test',
    participants: ['other_test'],
    story_time: 120,
    discourse_order: Number(id),
    location: 'loc_test',
    goal: `Objetivo de la escena ${id}`,
    conflict: 'Algo se lo impide',
    outcome: 'yes-but',
    value_change: 'a → b (+)',
    entry_state: 'Estado de entrada',
    exit_state: 'Estado de salida',
    budget: 1000,
  }
}

function draft(id: string, body: string): Schemas['Draft'] {
  return { schema_version: 1, scene_ref: id, words: 1100, literal_tail: body, body }
}

const notFound = (detail: string) => HttpResponse.json({ error: 'not_found', detail }, { status: 404 })

/** The table of contents: ch01 = 001, 002; ch02 = 003. */
function serveToc() {
  server.use(
    http.get('/structure/chapters', ({ response }) =>
      response(200).json({
        schema_version: 1,
        chapters: [
          { id: 'ch01', function: 'f1', arc: 'a', budget: 1, target_tension_in: 1, target_tension_out: 2, scenes: ['001', '002'] },
          { id: 'ch02', function: 'f2', arc: 'a', budget: 1, target_tension_in: 2, target_tension_out: 3, scenes: ['003'] },
        ],
      }),
    ),
    http.get('/scenes', ({ response }) => response(200).json(['001', '002', '003'])),
  )
}

/** Every scene exists; a draft exists for the ids in `bodies`, the others answer 404. */
function serveScenes(bodies: Record<string, string>) {
  server.use(
    http.get('/scenes/{id}', ({ params, response }) => response(200).json(scene(params.id))),
    http.get('/manuscript/{id}', ({ params, response }) => {
      const body = bodies[params.id]
      return body === undefined
        ? response.untyped(notFound(`no draft for ${params.id}`))
        : response(200).json(draft(params.id, body))
    }),
  )
}

function renderScene(id: string) {
  return renderWithProviders(
    <Routes>
      <Route path="/scenes/*" element={<ScenesRoutes />} />
    </Routes>,
    { route: `/scenes/${id}` },
  )
}

describe('ScenePage', () => {
  // spec 002 / AC 9
  it('shows a skeleton, then the record headline and the draft rendered as Markdown', async () => {
    serveToc()
    serveScenes({ '002': 'Primer párrafo con *énfasis*.\n\nSegundo párrafo.' })
    const { container } = renderScene('002')
    expect(screen.getByRole('status')).toHaveTextContent('Cargando…')
    expect(await screen.findByRole('heading', { level: 1, name: 'Escena 002' })).toBeInTheDocument()
    expect(screen.getByText('Objetivo de la escena 002')).toBeInTheDocument()
    for (const value of ['pov_test', 'loc_test', '120', 'Algo se lo impide', 'yes-but']) {
      expect(screen.getByText(value)).toBeInTheDocument()
    }
    expect(screen.getByText('1100 palabras')).toBeInTheDocument()
    const em = container.querySelector('.prose em')
    expect(em).toHaveTextContent('énfasis')
    expect(container.querySelectorAll('.prose p')).toHaveLength(2)
  })

  // spec 002 / AC 9 (FR-SCN-03)
  it('links previous and next across a chapter boundary, and following next opens it', async () => {
    serveToc()
    serveScenes({ '002': 'Dos.', '003': 'Tres.' })
    renderScene('002')
    const nav = await screen.findByRole('navigation', { name: 'Escenas vecinas' })
    const next = await within(nav).findByRole('link', { name: 'Siguiente: 003' })
    expect(within(nav).getByRole('link', { name: 'Anterior: 001' })).toHaveAttribute('href', '/scenes/001')
    await userEvent.click(next)
    expect(await screen.findByRole('heading', { level: 1, name: 'Escena 003' })).toBeInTheDocument()
    expect(await screen.findByText('Tres.')).toBeInTheDocument()
    expect(screen.queryByRole('link', { name: /^Siguiente/ })).not.toBeInTheDocument()
  })

  // spec 002 / AC 9 (FR-SCN-02)
  it('shows the record and the empty state when the draft is a 404', async () => {
    serveToc()
    serveScenes({})
    renderScene('001')
    expect(await screen.findByText('Esta escena aún no tiene borrador')).toBeInTheDocument()
    expect(screen.getByText('Objetivo de la escena 001')).toBeInTheDocument()
    expect(screen.queryByRole('alert')).not.toBeInTheDocument()
  })

  // spec 002 / AC 9
  it('shows not-found, without a retry, when the scene is a 404', async () => {
    serveToc()
    server.use(
      http.get('/scenes/{id}', ({ response }) => response.untyped(notFound('scene 999 does not exist'))),
      http.get('/manuscript/{id}', ({ response }) => response.untyped(notFound('no draft'))),
    )
    renderScene('999')
    expect(await screen.findByRole('heading', { name: 'Escena no encontrada' })).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Volver al índice' })).toHaveAttribute('href', '/scenes')
    expect(screen.queryByRole('button', { name: 'Reintentar' })).not.toBeInTheDocument()
  })

  // spec 002 / AC 9 (FR-SCN-06)
  it('shows not-found for a malformed id without issuing any request', async () => {
    const requests: string[] = []
    const record = ({ request }: { request: Request }) => {
      requests.push(request.url)
    }
    server.events.on('request:start', record)
    try {
      renderScene('abc')
      expect(await screen.findByRole('heading', { name: 'Escena no encontrada' })).toBeInTheDocument()
      // Give any query a chance to fire before counting.
      await new Promise((resolve) => setTimeout(resolve, 50))
      expect(requests).toEqual([])
      expect(screen.queryByRole('button', { name: 'Reintentar' })).not.toBeInTheDocument()
    } finally {
      server.events.removeListener('request:start', record)
    }
  })

  // spec 002 / AC 9
  it('shows a generic message with the status on a non-JSON 500, and retrying recovers', async () => {
    serveToc()
    serveScenes({ '002': 'Recuperada.' })
    let calls = 0
    server.use(
      http.get('/scenes/{id}', ({ params, response }) => {
        calls += 1
        return calls === 1
          ? response.untyped(new HttpResponse('boom', { status: 500 }))
          : response(200).json(scene(params.id))
      }),
    )
    renderScene('002')
    const alert = await screen.findByRole('alert')
    expect(alert).toHaveTextContent('Error del servidor (HTTP 500)')
    await userEvent.click(within(alert).getByRole('button', { name: 'Reintentar' }))
    expect(await screen.findByText('Recuperada.')).toBeInTheDocument()
  })

  it('shows the error panel when the draft fails with anything but a 404', async () => {
    serveToc()
    serveScenes({})
    server.use(
      http.get('/manuscript/{id}', ({ response }) =>
        response.untyped(HttpResponse.json({ error: 'invalid_record', detail: 'borrador corrupto' }, { status: 422 })),
      ),
    )
    renderScene('002')
    const alert = await screen.findByRole('alert')
    expect(alert).toHaveTextContent('borrador corrupto')
    expect(within(alert).getByRole('button', { name: 'Reintentar' })).toBeInTheDocument()
  })

  // spec 002 / AC 9 (FR-TOOL-05, P15)
  it('renders raw HTML in the draft body as text, never as an element', async () => {
    serveToc()
    serveScenes({
      '002': '<script>alert(1)</script>\n\nAntes <img src=x onerror=alert(1)> después.\n\n<img src=y onerror=alert(2)>',
    })
    const { container } = renderScene('002')
    await screen.findByText('1100 palabras')
    const prose = container.querySelector('.prose')
    expect(prose).not.toBeNull()
    expect(prose).toHaveTextContent('<script>alert(1)</script>')
    expect(prose).toHaveTextContent('<img src=x onerror=alert(1)>')
    expect(prose).toHaveTextContent('<img src=y onerror=alert(2)>')
    expect(container.querySelector('script, img')).toBeNull()
    expect(document.querySelector('[onerror]')).toBeNull()
  })
})
