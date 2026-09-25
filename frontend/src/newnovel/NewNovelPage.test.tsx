// The "Nueva novela" wizard over the typed MSW server (spec 020): the review step shows the
// validation report in Spanish and blocks submit; a valid brief is posted and the page switches
// to the generation's progress.
import { fireEvent, screen } from '@testing-library/react'
import { Route, Routes } from 'react-router'
import { describe, expect, it } from 'vitest'

import { renderWithProviders } from '../../test/render'
import { http, server } from '../../test/server'
import { NewNovelRoute } from './index'

function renderPage() {
  renderWithProviders(
    <Routes>
      <Route path="/nueva" element={<NewNovelRoute />} />
    </Routes>,
    { route: '/nueva' },
  )
}

describe('new novel wizard (spec 020)', () => {
  // spec 020 / AC 5
  it('shows missing fields and contradictions in Spanish and blocks submit', async () => {
    server.use(
      http.post('/interview/validate', ({ response }) =>
        response(200).json({
          valid: false,
          missing: ['dedication'],
          contradictions: ['recipient.age=6 vs genre=romance: el romance no es apto para menos de 12 años'],
          errors: [],
        }),
      ),
    )
    renderPage()
    fireEvent.click(screen.getByRole('button', { name: 'Paso 5: Dedicatoria y revisión' }))
    expect(await screen.findByText('Falta la dedicatoria.')).toBeInTheDocument()
    expect(screen.getByText(/El romance no es apto para menos de 12 años \(la edad: 6/)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Generar novela' })).toBeDisabled()
  })

  // spec 020 / AC 5
  it('posts the brief and shows the progress', async () => {
    let posted: unknown = null
    server.use(
      http.post('/interview/validate', ({ response }) =>
        response(200).json({ valid: true, missing: [], contradictions: [], errors: [] }),
      ),
      http.post('/novels/generate', async ({ request, response }) => {
        posted = await request.json()
        return response(202).json({ novel_id: 'nv-1', job_id: 'j1' })
      }),
      http.get('/novels/{novel_id}/generation', ({ response }) =>
        response(200).json({
          novel_id: 'nv-1',
          status: 'running',
          phase: 'writing',
          chapters_done: 2,
          chapters_total: 10,
          cost_usd: 0.84,
          calls: 31,
          issues: [],
          detail: '',
        }),
      ),
    )
    renderPage()
    fireEvent.click(screen.getByRole('button', { name: 'Rellenar con ejemplo' }))
    fireEvent.click(screen.getByRole('button', { name: 'Paso 5: Dedicatoria y revisión' }))
    expect(await screen.findByText(/La ficha está completa/)).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'Generar novela' }))
    expect(await screen.findByText('Capítulos escritos: 2 de 10')).toBeInTheDocument()
    expect(screen.getByText('Escribiendo el capítulo 3 de 10…')).toBeInTheDocument()
    expect(posted).toMatchObject({
      chapters: 10,
      brief: { recipient: { age: 65, traits: ['paciente', 'bromista', 'curioso', 'generoso con su tiempo'] }, genre: 'aventura' },
    })
  })
})
