// `/scenes` in its four states, from MSW handlers. Spec 002, FR-SCN route table, AC 8.
import { screen, within } from '@testing-library/react'
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

// spec 003 (FR-BOOK): `/scenes` also reads the project record for its book header.
function projectHandler() {
  return http.get('/canon/project', ({ response }) =>
    response(200).json({
      schema_version: 1,
      premise: { statement: 'Premisa de prueba', dramatic_question: '¿Pregunta de prueba?', answer: 'Respuesta de prueba' },
      thesis: { proposition: 'Tesis de prueba', antithesis: 'Antítesis de prueba' },
      genre_contract: { subgenre: 'sf_test', rigour: 'rigor de prueba', limits: 'límites de prueba' },
      body: '',
    }),
  )
}

function serveToc(chapters: Schemas['Chapter'][], ids: string[]) {
  server.use(
    http.get('/structure/chapters', ({ response }) => response(200).json({ schema_version: 1, chapters })),
    http.get('/scenes', ({ response }) => response(200).json(ids)),
    projectHandler(),
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

function sectionOf(headingName: string): HTMLElement {
  const section = screen.getByRole('heading', { level: 2, name: headingName }).closest('section')
  if (section === null) {
    throw new Error(`no section for ${headingName}`)
  }
  return section
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
      projectHandler(),
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
      projectHandler(),
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
    expect(screen.getAllByRole('heading', { level: 2 }).map((h) => h.textContent)).toEqual(['ch01', 'ch02'])
    expect(sectionOf('ch01')).toHaveTextContent('Función dramática de ch01')
    expect(linkNames(sectionOf('ch01'))).toEqual(['Escena 003', 'Escena 001'])
    expect(linkNames(sectionOf('ch02'))).toEqual(['Escena 002'])
    expect(screen.getByRole('link', { name: 'Escena 003' })).toHaveAttribute('href', '/scenes/003')
    expect(screen.queryByRole('heading', { name: 'Sin capítulo' })).not.toBeInTheDocument()
  })

  // spec 002 / AC 8
  it('lists a scene no chapter names last, under "Sin capítulo"', async () => {
    serveToc([chapter('ch01', ['002'])], ['004', '002'])
    renderToc()
    await screen.findByRole('link', { name: 'Escena 004' })
    expect(screen.getAllByRole('heading', { level: 2 }).map((h) => h.textContent)).toEqual(['ch01', 'Sin capítulo'])
    expect(linkNames(sectionOf('Sin capítulo'))).toEqual(['Escena 004'])
    expect(screen.getAllByRole('link').map((link) => link.textContent)).toEqual(['Escena 002', 'Escena 004'])
  })
})
