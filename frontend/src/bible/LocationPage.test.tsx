// `/locations/:id` in its states, from typed MSW handlers. Spec 003, FR-BIBLE-04, FR-BIBLE-05, AC 17.
import { screen, waitFor, within } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import { failSceneRecords, renderBible, serveBible } from './testing'

function facts(): Record<string, string | null | undefined> {
  const card = screen.getByRole('heading', { level: 2, name: 'Ficha' }).closest('section')
  if (card === null) throw new Error('no facts card')
  return Object.fromEntries(
    [...card.querySelectorAll('dt')].map((dt) => [dt.textContent, dt.nextElementSibling?.textContent]),
  )
}

describe('LocationPage', () => {
  // spec 003 / AC 17
  it('shows the derived name, the parent as a link, the key-value card and the body', async () => {
    serveBible()
    const { container } = renderBible('/locations/pump_vault')
    expect(screen.getAllByRole('status')[0]).toHaveTextContent('Cargando…')
    expect(await screen.findByRole('heading', { level: 1, name: 'Pump vault' })).toBeInTheDocument()
    expect(screen.getAllByRole('heading', { level: 1 })).toHaveLength(1)
    expect(screen.getByText('Lugar')).toHaveClass('eyebrow')
    const parentLine = screen.getByText(/^Dentro de/)
    expect(within(parentLine).getByRole('link', { name: 'Kestrel deep' })).toHaveAttribute(
      'href',
      '/locations/kestrel_deep',
    )
    await waitFor(() => {
      expect(facts()['Sublugares']).toBe('Ninguno')
    })
    expect(facts()).toEqual({
      'Paleta sensorial': 'four-degree brine, absolute black past four metres',
      Geometría: 'eleven metres from the throat to the core cradle',
      Accesos: 'desde Kestrel deep · 6 h',
      Sublugares: 'Ninguno',
    })
    expect(container.querySelector('.prose em')).toHaveTextContent('pump vault')
    expect(screen.getByRole('link', { name: 'Todos los lugares' })).toHaveAttribute('href', '/locations')
    await waitFor(() => {
      expect(document.title).toBe('Pump vault · Lugares · My Story Marker')
    })
  })

  // spec 003 / AC 17
  it('marks a leaf location\'s scenes as set here, each linking to its chapter anchor', async () => {
    serveBible()
    renderBible('/locations/pump_vault')
    const region = await screen.findByRole('region', { name: 'Aparece en' })
    await within(region).findByRole('link', { name: 'Capítulo 1 The Sealed Half' })
    const scenes = within(region)
      .getAllByRole('link', { name: /^Escena/ })
      .map((a) => [a.textContent, a.getAttribute('href')])
    expect(scenes).toEqual([
      ['Escena 002 · aquí', '/chapters/ch01#scene-002'],
      ['Escena 003 · aquí', '/chapters/ch01#scene-003'],
      ['Escena 004 · aquí', '/chapters/ch02#scene-004'],
      ['Escena 006 · aquí', '/chapters/ch02#scene-006'],
    ])
  })

  // spec 003 / AC 17
  it('shows a root with its sublocations, and counts their scenes via the sublocation', async () => {
    serveBible()
    renderBible('/locations/kestrel_deep')
    expect(await screen.findByRole('heading', { level: 1, name: 'Kestrel deep' })).toBeInTheDocument()
    expect(screen.getByText('Lugar raíz')).toBeInTheDocument()
    const region = screen.getByRole('region', { name: 'Aparece en' })
    expect(await within(region).findByRole('link', { name: 'Escena 002 · vía Pump vault' })).toHaveAttribute(
      'href',
      '/chapters/ch01#scene-002',
    )
    expect(within(region).getByRole('link', { name: 'Escena 001 · aquí' })).toHaveAttribute(
      'href',
      '/chapters/ch01#scene-001',
    )
    expect(within(region).getByRole('link', { name: 'Capítulo 2 The Calving Window' })).toHaveAttribute(
      'href',
      '/chapters/ch02',
    )
    expect(screen.getByText('Aparece en 2 capítulos')).toHaveClass('pill')
    const sublocations = screen.getByText('Sublugares').nextElementSibling
    if (!(sublocations instanceof HTMLElement)) throw new Error('no sublocations')
    expect(within(sublocations).getByRole('link', { name: 'Pump vault' })).toHaveAttribute('href', '/locations/pump_vault')
  })

  // spec 003 / AC 17 (FR-BIBLE-05)
  it('renders the sheet with the appearances notice when scene records fail', async () => {
    serveBible()
    failSceneRecords()
    renderBible('/locations/kestrel_deep')
    expect(await screen.findByRole('heading', { level: 1, name: 'Kestrel deep' })).toBeInTheDocument()
    const region = screen.getByRole('region', { name: 'Aparece en' })
    expect(await within(region).findByText('No se han podido calcular las apariciones')).toBeInTheDocument()
    expect(screen.getByText('dry cold, hot brass off the exchanger trunks')).toBeInTheDocument()
    expect(screen.queryByRole('alert')).not.toBeInTheDocument()
  })

  // spec 003 / AC 17
  it('shows not-found, without a retry, for an unknown id', async () => {
    serveBible()
    renderBible('/locations/atlantis')
    expect(await screen.findByRole('heading', { level: 1, name: 'Lugar no encontrado' })).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Volver a Lugares' })).toHaveAttribute('href', '/locations')
    expect(screen.queryByRole('button', { name: 'Reintentar' })).not.toBeInTheDocument()
  })
})
