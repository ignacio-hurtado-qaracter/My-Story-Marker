// The cover at `/`, from MSW handlers. Spec 003, FR-COVER-01..04, AC 5; plan 003 Q11.
//
// jsdom has no WebGL: the canvas probe is stubbed to fail (as jsdom would, but without its
// "not implemented" noise), so the cover's decorative planet shows its still picture and no
// test here loads three.js (the moving planet is AC 8's Playwright run).
import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { HttpResponse } from 'msw'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { renderWithProviders } from '../../test/render'
import { http, server } from '../../test/server'
import type { Schemas } from '../shared/api'
import { CoverPage } from './CoverPage'
import { STORAGE_KEY } from './useCoverSettings'

// From backend/tests/fixtures/repo/canon/project.md.
const STATEMENT =
  'Teodora Vance, the last soak-certified diver at Kestrel Deep, wants to lift the drowned Kestrel core out of the flooded pump vault before the co-op sealing order closes it forever.'
const QUESTION = 'Does the core come up before the vault is sealed, and what does Vance spend of her brother to do it?'
const ANSWER = 'It comes up, inside the last window, because Ilan gives back what the co-op left him.'

const PROJECT: Schemas['Project'] = {
  schema_version: 1,
  premise: { statement: STATEMENT, dramatic_question: QUESTION, answer: ANSWER },
  thesis: {
    proposition: 'What a person is owed cannot be signed away by the institution that owes it.',
    antithesis: 'A signature is consent and the indemnity was mercy.',
    test_scenes: ['002'],
  },
  genre_contract: {
    subgenre: 'Hard SF, close focus',
    rigour: 'Pressure, cold, dark and co-op law hold as the axioms state them.',
    limits: 'No rescue from off Nix.',
    promises: [{ promise: 'The reader learns what the read-key is.', payoff_scene: '005' }],
  },
  body: 'A salvage story on the surface, an argument about consent underneath.',
}

function chapter(id: string, scenes: string[]): Schemas['Chapter'] {
  return { id, function: `"Título de ${id}": función.`, arc: 'ar_descent', budget: 1000, target_tension_in: 1, target_tension_out: 2, scenes }
}

const CHAPTERS = [chapter('ch01', ['001', '002', '003']), chapter('ch02', ['004', '005', '006'])]

interface Book {
  project?: 'ok' | 'fail'
  chapters?: Schemas['Chapter'][] | 'fail'
}

function serveBook({ project = 'ok', chapters = CHAPTERS }: Book = {}) {
  server.use(
    http.get('/canon/project', ({ response }) =>
      project === 'ok'
        ? response(200).json(PROJECT)
        : response.untyped(HttpResponse.json({ error: 'StoreUnavailable', detail: 'Fallo de prueba' }, { status: 500 })),
    ),
    http.get('/structure/chapters', ({ response }) =>
      chapters === 'fail'
        ? response.untyped(HttpResponse.json({ error: 'StoreUnavailable', detail: 'Fallo de prueba' }, { status: 500 }))
        : response(200).json({ schema_version: 1, chapters }),
    ),
  )
}

function renderCover() {
  return renderWithProviders(<CoverPage />, { route: '/' })
}

function dedicationCard(): HTMLElement {
  return screen.getByRole('region', { name: 'Dedicatoria' })
}

async function personalise(values: { title?: string; to?: string; dedication?: string; from?: string }) {
  const user = userEvent.setup()
  await user.click(screen.getByRole('button', { name: 'Personalizar portada' }))
  const fields: [string, string | undefined][] = [
    ['Título', values.title],
    ['Para', values.to],
    ['Dedicatoria', values.dedication],
    ['De', values.from],
  ]
  for (const [label, value] of fields) {
    if (value === undefined) continue
    const field = screen.getByRole('textbox', { name: label })
    await user.clear(field)
    await user.type(field, value)
  }
  return user
}

beforeEach(() => {
  window.localStorage.clear()
  // No WebGL, quietly (restoreMocks puts the real method back after each test).
  vi.spyOn(HTMLCanvasElement.prototype, 'getContext').mockImplementation(() => null)
})

afterEach(() => {
  window.localStorage.clear()
})

describe('CoverPage', () => {
  // spec 003 / AC 5
  it('shows the premise statement as the lead, and never the answer', async () => {
    serveBook()
    renderCover()

    expect(await screen.findByText(STATEMENT)).toBeInTheDocument()
    expect(screen.getByRole('heading', { level: 1, name: 'Mi novela' })).toBeInTheDocument()
    expect(screen.getAllByRole('heading', { level: 1 })).toHaveLength(1)
    expect(screen.getByText('Novela')).toBeInTheDocument()
    // The answer is how the book ends: it is in the response, never on the page.
    await screen.findByRole('link', { name: 'Empezar a leer' })
    expect(document.body).not.toHaveTextContent(ANSWER)
    expect(document.title).toBe('Portada · My Story Marker')
  })

  // spec 003 / AC 5
  it('links "Empezar a leer" to the first chapter\'s reader and "Índice" to the index', async () => {
    serveBook()
    renderCover()

    expect(await screen.findByRole('link', { name: 'Empezar a leer' })).toHaveAttribute('href', '/chapters/ch01')
    expect(screen.getByRole('link', { name: 'Índice' })).toHaveAttribute('href', '/scenes')
  })

  // spec 003 / AC 5
  it('starts with the default title, no para or de lines, and the dedication placeholder', async () => {
    serveBook()
    renderCover()
    await screen.findByText(STATEMENT)

    const card = dedicationCard()
    expect(within(card).getByText('Personaliza la portada para escribir aquí tu dedicatoria.')).toBeInTheDocument()
    expect(within(card).queryByText(/^Para /)).not.toBeInTheDocument()
    expect(within(card).queryByText(/^— /)).not.toBeInTheDocument()
    expect(screen.queryByRole('form', { name: 'Personalizar portada' })).not.toBeInTheDocument()
  })

  // spec 003 / AC 5
  it('saves the personalised cover, shows it, and keeps it across a remount', async () => {
    serveBook()
    const first = renderCover()
    await screen.findByText(STATEMENT)

    const user = await personalise({
      title: 'La mitad sellada',
      to: 'Ilan',
      dedication: 'Para quien bajó a la oscuridad y volvió.',
      from: 'Teodora',
    })
    expect(screen.getByLabelText('Título')).toBeInTheDocument()
    expect(screen.getByText('Se guarda solo en este navegador.')).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'Guardar' }))

    expect(screen.getByRole('heading', { level: 1, name: 'La mitad sellada' })).toBeInTheDocument()
    const card = dedicationCard()
    expect(within(card).getByText('Para Ilan')).toBeInTheDocument()
    expect(within(card).getByText('Para quien bajó a la oscuridad y volvió.')).toBeInTheDocument()
    expect(within(card).getByText('— Teodora')).toBeInTheDocument()
    expect(within(card).queryByText('Personaliza la portada para escribir aquí tu dedicatoria.')).not.toBeInTheDocument()
    // The form closes and focus returns to the button that opened it.
    expect(screen.queryByRole('form', { name: 'Personalizar portada' })).not.toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Personalizar portada' })).toHaveFocus()
    await waitFor(() => {
      expect(document.title).toBe('La mitad sellada · My Story Marker')
    })
    expect(JSON.parse(window.localStorage.getItem(STORAGE_KEY) ?? 'null')).toEqual({
      title: 'La mitad sellada',
      to: 'Ilan',
      dedication: 'Para quien bajó a la oscuridad y volvió.',
      from: 'Teodora',
    })

    first.unmount()
    renderCover()

    expect(screen.getByRole('heading', { level: 1, name: 'La mitad sellada' })).toBeInTheDocument()
    expect(within(dedicationCard()).getByText('Para Ilan')).toBeInTheDocument()
    expect(within(dedicationCard()).getByText('— Teodora')).toBeInTheDocument()
  })

  // spec 003 / AC 5
  it('discards the edits on "Cancelar" and on Escape', async () => {
    const saved = { title: 'La mitad sellada', to: 'Ilan', dedication: 'Para quien volvió.', from: 'Teodora' }
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify(saved))
    serveBook()
    renderCover()
    expect(screen.getByRole('heading', { level: 1, name: 'La mitad sellada' })).toBeInTheDocument()

    const user = await personalise({ title: 'Otro título', to: 'Nadie' })
    await user.click(screen.getByRole('button', { name: 'Cancelar' }))

    expect(screen.queryByRole('form', { name: 'Personalizar portada' })).not.toBeInTheDocument()
    expect(screen.getByRole('heading', { level: 1, name: 'La mitad sellada' })).toBeInTheDocument()
    expect(within(dedicationCard()).getByText('Para Ilan')).toBeInTheDocument()
    expect(screen.queryByText('Para Nadie')).not.toBeInTheDocument()
    expect(JSON.parse(window.localStorage.getItem(STORAGE_KEY) ?? 'null')).toEqual(saved)

    // Reopened, the form starts again from the saved values; Escape closes it too.
    await user.click(screen.getByRole('button', { name: 'Personalizar portada' }))
    expect(screen.getByLabelText('Título')).toHaveValue('La mitad sellada')
    expect(screen.getByLabelText('Título')).toHaveFocus()
    await user.type(screen.getByLabelText('Para'), ' y nadie más')
    await user.keyboard('{Escape}')
    expect(screen.queryByRole('form', { name: 'Personalizar portada' })).not.toBeInTheDocument()
    expect(within(dedicationCard()).getByText('Para Ilan')).toBeInTheDocument()
  })

  // spec 003 / AC 5
  it('still shows the saved values when localStorage throws', async () => {
    vi.spyOn(Storage.prototype, 'getItem').mockImplementation(() => {
      throw new DOMException('Acceso denegado', 'SecurityError')
    })
    vi.spyOn(Storage.prototype, 'setItem').mockImplementation(() => {
      throw new DOMException('Sin espacio', 'QuotaExceededError')
    })
    serveBook()
    renderCover()
    expect(screen.getByRole('heading', { level: 1, name: 'Mi novela' })).toBeInTheDocument()

    const user = await personalise({ title: 'La mitad sellada', dedication: 'Para quien volvió.', from: 'Teodora' })
    await user.click(screen.getByRole('button', { name: 'Guardar' }))

    expect(screen.getByRole('heading', { level: 1, name: 'La mitad sellada' })).toBeInTheDocument()
    expect(within(dedicationCard()).getByText('Para quien volvió.')).toBeInTheDocument()
    expect(within(dedicationCard()).getByText('— Teodora')).toBeInTheDocument()
    expect(screen.getByRole('status')).toHaveTextContent('No se ha podido guardar en este navegador')
  })

  // spec 003 / AC 5
  it('omits only the lead when the premise fails', async () => {
    serveBook({ project: 'fail' })
    renderCover()

    expect(await screen.findByRole('link', { name: 'Empezar a leer' })).toHaveAttribute('href', '/chapters/ch01')
    await waitFor(() => {
      expect(document.querySelector('.cover-lead-skeleton')).toBeNull()
    })
    expect(screen.queryByText(STATEMENT)).not.toBeInTheDocument()
    expect(screen.getByRole('heading', { level: 1, name: 'Mi novela' })).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Índice' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Personalizar portada' })).toBeInTheDocument()
    expect(screen.queryByRole('alert')).not.toBeInTheDocument()
  })

  // spec 003 / AC 5 (FR-COVER-04)
  it('points "Empezar a leer" to the index when the chapters fail', async () => {
    serveBook({ chapters: 'fail' })
    renderCover()

    expect(await screen.findByRole('link', { name: 'Empezar a leer' })).toHaveAttribute('href', '/scenes')
    expect(await screen.findByText(STATEMENT)).toBeInTheDocument()
    expect(screen.queryByRole('alert')).not.toBeInTheDocument()
  })

  // spec 003 / AC 5 (FR-COVER-04)
  it('hides "Empezar a leer" when the book has no chapters, and keeps "Índice"', async () => {
    serveBook({ chapters: [] })
    renderCover()

    await screen.findByText(STATEMENT)
    await waitFor(() => {
      expect(document.querySelector('.cover-btn-skeleton')).toBeNull()
    })
    expect(screen.queryByRole('link', { name: 'Empezar a leer' })).not.toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Índice' })).toHaveAttribute('href', '/scenes')
  })

  // spec 003 / AC 5 (FR-COVER-01: the planet is decoration)
  it('shows a still planet, with no error and no toggle, when WebGL is unavailable', async () => {
    serveBook()
    renderCover()
    await screen.findByText(STATEMENT)

    expect(document.querySelector('.cover-planet .planet-still')).not.toBeNull()
    expect(screen.queryByRole('alert')).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Pausar animación' })).not.toBeInTheDocument()
  })
})
