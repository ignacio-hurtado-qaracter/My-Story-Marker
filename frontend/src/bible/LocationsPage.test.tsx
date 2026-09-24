// `/locations` in its states, from typed MSW handlers. Spec 003, FR-BIBLE-04, FR-BIBLE-05, AC 17.
import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { HttpResponse } from 'msw'
import { describe, expect, it } from 'vitest'

import { http, server } from '../../test/server'
import { renderBible, serveBible } from './testing'

function card(name: string): HTMLElement {
  const item = screen.getByRole('link', { name }).closest('li')
  if (item === null) throw new Error(`no card for ${name}`)
  return item
}

describe('LocationsPage', () => {
  // spec 003 / AC 17
  it('shows a card per location with its derived name, its parent, its palette and its chapters', async () => {
    serveBible()
    renderBible('/locations')
    expect(screen.getByRole('status')).toHaveTextContent('Cargando…')
    expect(screen.getByRole('heading', { level: 1, name: 'Lugares' })).toBeInTheDocument()
    expect(await screen.findByRole('link', { name: 'Kestrel deep' })).toHaveAttribute('href', '/locations/kestrel_deep')
    const root = card('Kestrel deep')
    const vault = card('Pump vault')
    expect(within(vault).getByRole('link', { name: 'Pump vault' })).toHaveAttribute('href', '/locations/pump_vault')
    expect(within(root).getByText('Lugar raíz')).toBeInTheDocument()
    expect(within(vault).getByText('Dentro de Kestrel deep')).toBeInTheDocument()
    expect(within(vault).getByText('four-degree brine, absolute black past four metres')).toBeInTheDocument()
    expect(within(vault).getByText('PV').closest('[aria-hidden="true"]')).not.toBeNull()
    expect(await within(vault).findByRole('link', { name: 'Capítulo 1' })).toHaveAttribute('href', '/chapters/ch01')
    expect(within(root).getByRole('link', { name: 'Capítulo 2' })).toHaveAttribute('href', '/chapters/ch02')
    expect(screen.getByText('2 lugares')).toHaveClass('pill')
    await waitFor(() => {
      expect(document.title).toBe('Lugares · My Story Marker')
    })
  })

  // spec 003 / AC 17
  it('shows the empty state when there are no locations', async () => {
    serveBible({ locations: [] })
    renderBible('/locations')
    expect(await screen.findByText('Todavía no hay lugares')).toBeInTheDocument()
  })

  // spec 003 / AC 17 (FR-BIBLE-05)
  it('shows the error panel when the list fails, and retrying recovers', async () => {
    serveBible()
    let calls = 0
    server.use(
      http.get('/canon/locations', ({ response }) => {
        calls += 1
        return calls === 1
          ? response.untyped(new HttpResponse('boom', { status: 500 }))
          : response(200).json({ kind: 'locations', ids: ['pump_vault'] })
      }),
    )
    renderBible('/locations')
    const alert = await screen.findByRole('alert')
    expect(alert).toHaveTextContent('Error del servidor (HTTP 500)')
    await userEvent.click(within(alert).getByRole('button', { name: 'Reintentar' }))
    expect(await screen.findByRole('link', { name: 'Pump vault' })).toBeInTheDocument()
  })
})
