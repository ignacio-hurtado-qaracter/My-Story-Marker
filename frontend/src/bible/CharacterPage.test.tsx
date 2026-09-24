// `/characters/:id` in its states, from typed MSW handlers. Spec 003, FR-BIBLE-03, FR-BIBLE-05,
// AC 17.
import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { HttpResponse } from 'msw'
import { describe, expect, it } from 'vitest'

import { http, server } from '../../test/server'
import { SCENES, failSceneRecords, renderBible, scene, serveBible } from './testing'

describe('CharacterPage', () => {
  // spec 003 / AC 17
  it('shows a skeleton, then the detail head, the key-value card and the body as Markdown', async () => {
    serveBible()
    const { container } = renderBible('/characters/vance')
    expect(screen.getAllByRole('status')[0]).toHaveTextContent('Cargando…')
    expect(await screen.findByRole('heading', { level: 1, name: 'Teodora Vance' })).toBeInTheDocument()
    expect(screen.getAllByRole('heading', { level: 1 })).toHaveLength(1)
    expect(screen.getByText('Personaje')).toHaveClass('eyebrow')
    expect(screen.getByText('TV')).toHaveAttribute('aria-hidden', 'true')
    const facts = screen.getByRole('heading', { level: 2, name: 'Ficha' }).closest('section')
    if (facts === null) throw new Error('no facts card')
    const rows = Object.fromEntries(
      [...facts.querySelectorAll('dt')].map((dt) => [dt.textContent, dt.nextElementSibling?.textContent]),
    )
    expect(rows).toEqual({
      Quiere: 'the vault kept open long enough to lift the Kestrel core',
      Necesita: 'Lo que Teodora Vance necesita',
      Mentira: 'La mentira de Teodora Vance',
      Competencias: 'soak-certified for unaccompanied vault workreads a core cradle by touch alone',
      Build: 'short, heavy through the shoulders',
      'Left forearm': 'co-op dive certification tattoo',
    })
    expect(within(facts).getAllByRole('listitem')).toHaveLength(2)
    expect(container.querySelector('.prose h2')).toHaveTextContent('La bifurcación')
    expect(container.querySelector('.prose em')).toHaveTextContent('quiere')
    expect(screen.getByRole('link', { name: 'Todos los personajes' })).toHaveAttribute('href', '/characters')
    await waitFor(() => {
      expect(document.title).toBe('Teodora Vance · Personajes · My Story Marker')
    })
  })

  // spec 003 / AC 17
  it('lists "Aparece en" by chapter, linking each chapter and each scene anchor, with the role', async () => {
    serveBible()
    renderBible('/characters/vance')
    const region = await screen.findByRole('region', { name: 'Aparece en' })
    const chapterOne = await within(region).findByRole('link', { name: 'Capítulo 1 The Sealed Half' })
    expect(chapterOne).toHaveAttribute('href', '/chapters/ch01')
    expect(within(region).getByRole('link', { name: 'Capítulo 2 The Calving Window' })).toHaveAttribute(
      'href',
      '/chapters/ch02',
    )
    const scenes = within(region)
      .getAllByRole('link', { name: /^Escena/ })
      .map((a) => [a.textContent, a.getAttribute('href')])
    expect(scenes).toEqual([
      ['Escena 001 · punto de vista', '/chapters/ch01#scene-001'],
      ['Escena 003 · punto de vista', '/chapters/ch01#scene-003'],
      ['Escena 004 · punto de vista', '/chapters/ch02#scene-004'],
      ['Escena 005 · presente', '/chapters/ch02#scene-005'],
      ['Escena 006 · punto de vista', '/chapters/ch02#scene-006'],
    ])
    expect(screen.getByText('Aparece en 2 capítulos')).toHaveClass('pill')
  })

  // spec 003 / AC 17
  it('groups a scene no chapter lists under "Sin capítulo", linking to the scene page', async () => {
    serveBible({ scenes: [...SCENES, scene('007', 'quiej', ['vance'], 'pump_vault')] })
    renderBible('/characters/vance')
    const region = await screen.findByRole('region', { name: 'Aparece en' })
    expect(await within(region).findByText('Sin capítulo')).toBeInTheDocument()
    expect(within(region).getByRole('link', { name: 'Escena 007 · presente' })).toHaveAttribute('href', '/scenes/007')
    // "Sin capítulo" is not a chapter: the pill still counts two.
    expect(screen.getByText('Aparece en 2 capítulos')).toBeInTheDocument()
  })

  // spec 003 / AC 17 (FR-BIBLE-05)
  it('renders the sheet with the appearances notice when scene records fail', async () => {
    serveBible()
    failSceneRecords()
    renderBible('/characters/ilan')
    expect(await screen.findByRole('heading', { level: 1, name: 'Ilan Vance' })).toBeInTheDocument()
    const region = screen.getByRole('region', { name: 'Aparece en' })
    expect(await within(region).findByText('No se han podido calcular las apariciones')).toBeInTheDocument()
    expect(screen.getByText('to be left alone with the certification he still has')).toBeInTheDocument()
    expect(screen.queryByText(/^Aparece en \d/)).not.toBeInTheDocument()
    expect(screen.queryByRole('alert')).not.toBeInTheDocument()
  })

  // spec 003 / AC 17
  it('shows not-found, without a retry, for an unknown id', async () => {
    serveBible()
    renderBible('/characters/nadie')
    expect(await screen.findByRole('heading', { level: 1, name: 'Personaje no encontrado' })).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Volver a Personajes' })).toHaveAttribute('href', '/characters')
    expect(screen.queryByRole('button', { name: 'Reintentar' })).not.toBeInTheDocument()
  })

  // spec 003 / AC 17
  it('shows not-found for a malformed id without issuing any request', async () => {
    const requests: string[] = []
    const record = ({ request }: { request: Request }) => {
      requests.push(request.url)
    }
    server.events.on('request:start', record)
    try {
      renderBible('/characters/Not%20An%20Id')
      expect(await screen.findByRole('heading', { level: 1, name: 'Personaje no encontrado' })).toBeInTheDocument()
      await new Promise((resolve) => setTimeout(resolve, 50))
      expect(requests).toEqual([])
    } finally {
      server.events.removeListener('request:start', record)
    }
  })

  // spec 003 / AC 17 (FR-BIBLE-05)
  it('shows the error panel when the record fails, and retrying recovers', async () => {
    serveBible()
    let calls = 0
    server.use(
      http.get('/cast/{id}', ({ response }) => {
        calls += 1
        return calls === 1
          ? response.untyped(new HttpResponse('boom', { status: 500 }))
          : response.untyped(HttpResponse.json({ error: 'not_found', detail: 'gone' }, { status: 404 }))
      }),
    )
    renderBible('/characters/vance')
    const alert = await screen.findByRole('alert')
    expect(alert).toHaveTextContent('Error del servidor (HTTP 500)')
    expect(screen.getByRole('heading', { level: 1, name: 'No se ha podido cargar el personaje' })).toBeInTheDocument()
    await userEvent.click(within(alert).getByRole('button', { name: 'Reintentar' }))
    expect(await screen.findByRole('heading', { level: 1, name: 'Personaje no encontrado' })).toBeInTheDocument()
  })
})
