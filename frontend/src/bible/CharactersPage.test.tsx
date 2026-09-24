// `/characters` in its states, from typed MSW handlers. Spec 003, FR-BIBLE-02, FR-BIBLE-05, AC 17.
import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { HttpResponse } from 'msw'
import { describe, expect, it } from 'vitest'

import { http, server } from '../../test/server'
import { failSceneRecords, renderBible, serveBible } from './testing'

function card(name: string): HTMLElement {
  const item = screen.getByRole('link', { name }).closest('li')
  if (item === null) throw new Error(`no card for ${name}`)
  return item
}

describe('CharactersPage', () => {
  // spec 003 / AC 17
  it('shows a skeleton, then a card per character: name linking to the sheet, initials, wants', async () => {
    serveBible()
    renderBible('/characters')
    expect(screen.getByRole('status')).toHaveTextContent('Cargando…')
    expect(screen.getByRole('heading', { level: 1, name: 'Personajes' })).toBeInTheDocument()
    expect(await screen.findByRole('link', { name: 'Teodora Vance' })).toHaveAttribute('href', '/characters/vance')
    expect(screen.getByRole('link', { name: 'Ilan Vance' })).toHaveAttribute('href', '/characters/ilan')
    expect(screen.getByRole('link', { name: 'Marisol Quiej' })).toHaveAttribute('href', '/characters/quiej')
    expect(screen.getAllByRole('heading', { level: 2 }).map((h) => h.textContent)).toEqual([
      'Ilan Vance',
      'Marisol Quiej',
      'Teodora Vance',
    ])
    const vance = card('Teodora Vance')
    expect(within(vance).getByText('TV')).toHaveAttribute('aria-hidden', 'true')
    expect(within(vance).getByText('the vault kept open long enough to lift the Kestrel core')).toBeInTheDocument()
    expect(screen.getByText('3 personajes')).toHaveClass('pill')
    expect(screen.getAllByRole('heading', { level: 1 })).toHaveLength(1)
    await waitFor(() => {
      expect(document.title).toBe('Personajes · My Story Marker')
    })
  })

  // spec 003 / AC 17
  it('links each card to the chapters the character appears in, and says in how many scenes', async () => {
    serveBible()
    renderBible('/characters')
    await screen.findByRole('link', { name: 'Teodora Vance' })
    const vance = card('Teodora Vance')
    expect(await within(vance).findByRole('link', { name: 'Capítulo 1' })).toHaveAttribute('href', '/chapters/ch01')
    expect(within(vance).getByRole('link', { name: 'Capítulo 2' })).toHaveAttribute('href', '/chapters/ch02')
    expect(within(vance).getByText('Punto de vista en 4 escenas')).toBeInTheDocument()
    // Ilan is the POV of 002 (ch01) and present in 004 and 006 (ch02).
    const ilan = card('Ilan Vance')
    expect(within(ilan).getAllByRole('link', { name: /^Capítulo/ }).map((a) => a.getAttribute('href'))).toEqual([
      '/chapters/ch01',
      '/chapters/ch02',
    ])
    expect(within(ilan).getByText('Punto de vista en 1 escena')).toBeInTheDocument()
  })

  // spec 003 / AC 17 (FR-BIBLE-05)
  it('renders the cards with the appearances notice when scene records fail', async () => {
    serveBible()
    failSceneRecords()
    renderBible('/characters')
    expect(await screen.findByText('No se han podido calcular las apariciones')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Teodora Vance' })).toBeInTheDocument()
    expect(screen.queryByRole('link', { name: /^Capítulo/ })).not.toBeInTheDocument()
    expect(screen.queryByRole('alert')).not.toBeInTheDocument()
  })

  // spec 003 / AC 17
  it('shows the empty state when the cast is empty', async () => {
    serveBible({ characters: [] })
    renderBible('/characters')
    expect(await screen.findByText('Todavía no hay personajes')).toBeInTheDocument()
    expect(screen.queryByRole('status')).not.toBeInTheDocument()
  })

  // spec 003 / AC 17 (FR-BIBLE-05)
  it('shows the error panel when the cast fails, and retrying recovers', async () => {
    serveBible()
    let calls = 0
    server.use(
      http.get('/cast', ({ response }) => {
        calls += 1
        return calls === 1
          ? response.untyped(HttpResponse.json({ error: 'store_unavailable', detail: 'reparto ilegible' }, { status: 503 }))
          : response(200).json(['vance'])
      }),
    )
    renderBible('/characters')
    const alert = await screen.findByRole('alert')
    expect(alert).toHaveTextContent('reparto ilegible')
    await userEvent.click(within(alert).getByRole('button', { name: 'Reintentar' }))
    expect(await screen.findByRole('link', { name: 'Teodora Vance' })).toBeInTheDocument()
  })

  // spec 003 / AC 17
  it('shows the error panel when a character record fails', async () => {
    serveBible()
    server.use(
      http.get('/cast/{id}', ({ response }) => response.untyped(new HttpResponse('boom', { status: 500 }))),
    )
    renderBible('/characters')
    expect(await screen.findByRole('alert')).toHaveTextContent('Error del servidor (HTTP 500)')
  })
})
