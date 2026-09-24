// Test-only support for bible/: imported by bible/*.test.* and nothing else, so it never reaches
// the bundle. Story-bible data shaped like backend/tests/fixtures/repo/ (three characters, two
// chapters of three scenes, a root location and its child), typed MSW handlers for every route
// bible/ reads, and a renderer that mounts the feature's routes the way app/ does.
import { HttpResponse } from 'msw'
import { Route, Routes } from 'react-router'

import { renderWithProviders } from '../../test/render'
import { http, server } from '../../test/server'
import type { Schemas } from '../shared/api'
import { CharactersRoutes, LocationsRoutes } from './routes'

type Scene = Schemas['Scene']

function chapter(id: string, fn: string, scenes: string[]): Schemas['Chapter'] {
  return { id, function: fn, arc: 'ar_descent', budget: 3000, target_tension_in: 2, target_tension_out: 6, scenes }
}

export const CHAPTERS: Schemas['Chapter'][] = [
  chapter('ch01', '"The Sealed Half": every lawful way into the vault is closed to Vance.', ['001', '002', '003']),
  chapter('ch02', '“The Calving Window”: the sealing order stops being paper and becomes a clock.', [
    '004',
    '005',
    '006',
  ]),
]

export function scene(id: string, pov: string, participants: string[], location: string): Scene {
  return {
    schema_version: 1,
    id,
    pov,
    participants,
    location,
    story_time: 300,
    discourse_order: Number(id),
    goal: `Objetivo ${id}`,
    conflict: 'Conflicto',
    outcome: 'yes-but',
    value_change: 'a → b (+)',
    entry_state: 'Entrada',
    exit_state: 'Salida',
    budget: 1000,
  }
}

/** The fixture's six scenes: who is the POV, who is present, and where. */
export const SCENES: Scene[] = [
  scene('001', 'vance', ['quiej'], 'kestrel_deep'),
  scene('002', 'ilan', ['quiej'], 'pump_vault'),
  scene('003', 'vance', [], 'pump_vault'),
  scene('004', 'vance', ['ilan'], 'pump_vault'),
  scene('005', 'quiej', ['vance'], 'kestrel_deep'),
  scene('006', 'vance', ['ilan'], 'pump_vault'),
]

function character(
  id: string,
  name: string,
  wants: string,
  physical: Record<string, string>,
  competences: string[],
): Schemas['Character'] {
  return {
    schema_version: 1,
    id,
    name,
    wants,
    needs: `Lo que ${name} necesita`,
    lies: `La mentira de ${name}`,
    competences,
    immutable_physical: physical,
    arc: [],
    body: `${name} baja al pozo.\n\n## La bifurcación\n\nLo que *quiere* no es lo que necesita.`,
  }
}

export const CHARACTERS: Schemas['Character'][] = [
  character('ilan', 'Ilan Vance', 'to be left alone with the certification he still has', { left_hand: 'flesh' }, [
    'splices cradle seatings by feel',
  ]),
  character(
    'quiej',
    'Marisol Quiej',
    'the sealing order executed on schedule',
    { hands: 'burn-scarred from the exchanger fire' },
    ['co-op steward'],
  ),
  character(
    'vance',
    'Teodora Vance',
    'the vault kept open long enough to lift the Kestrel core',
    { build: 'short, heavy through the shoulders', left_forearm: 'co-op dive certification tattoo' },
    ['soak-certified for unaccompanied vault work', 'reads a core cradle by touch alone'],
  ),
]

export const LOCATIONS: Schemas['Location'][] = [
  {
    schema_version: 1,
    id: 'kestrel_deep',
    parent: null,
    sensory_palette: 'dry cold, hot brass off the exchanger trunks',
    geometry: 'a single bored gallery two hundred metres long',
    access: [{ from: 'pump_vault', hours: 6 }],
    body: 'The dry gallery is the half of Kestrel Deep that people live in.',
  },
  {
    schema_version: 1,
    id: 'pump_vault',
    parent: 'kestrel_deep',
    sensory_palette: 'four-degree brine, absolute black past four metres',
    geometry: 'eleven metres from the throat to the core cradle',
    access: [{ from: 'kestrel_deep', hours: 6 }],
    body: 'Below the gallery, past six hours of cold soak, the *pump vault*.',
  },
]

export const notFound = (detail: string) => HttpResponse.json({ error: 'not_found', detail }, { status: 404 })

export interface StoryBible {
  chapters?: Schemas['Chapter'][]
  scenes?: Scene[]
  characters?: Schemas['Character'][]
  locations?: Schemas['Location'][]
}

/** Serve a story bible on every route bible/ reads; unknown ids answer the IF-07 404. */
export function serveBible({
  chapters = CHAPTERS,
  scenes = SCENES,
  characters = CHARACTERS,
  locations = LOCATIONS,
}: StoryBible = {}) {
  server.use(
    http.get('/cast', ({ response }) => response(200).json(characters.map((c) => c.id))),
    http.get('/cast/{id}', ({ params, response }) => {
      const found = characters.find((c) => c.id === params.id)
      return found === undefined
        ? response.untyped(notFound(`character ${params.id} does not exist`))
        : response(200).json(found)
    }),
    http.get('/canon/locations', ({ response }) =>
      response(200).json({ kind: 'locations', ids: locations.map((l) => l.id) }),
    ),
    http.get('/canon/locations/{id}', ({ params, response }) => {
      const found = locations.find((l) => l.id === params.id)
      return found === undefined
        ? response.untyped(notFound(`location ${params.id} does not exist`))
        : response(200).json(found)
    }),
    http.get('/structure/chapters', ({ response }) => response(200).json({ schema_version: 1, chapters })),
    http.get('/scenes', ({ response }) => response(200).json(scenes.map((s) => s.id))),
    http.get('/scenes/{id}', ({ params, response }) => {
      const found = scenes.find((s) => s.id === params.id)
      return found === undefined
        ? response.untyped(notFound(`scene ${params.id} does not exist`))
        : response(200).json(found)
    }),
  )
}

/** Every scene record fails: appearances cannot be computed (FR-BIBLE-05). */
export function failSceneRecords() {
  server.use(
    http.get('/scenes/{id}', ({ response }) =>
      response.untyped(HttpResponse.json({ error: 'invalid_record', detail: 'escena corrupta' }, { status: 422 })),
    ),
  )
}

/** Render bible/'s routes as app/ mounts them, at `route`. */
export function renderBible(route: string) {
  return renderWithProviders(
    <Routes>
      <Route path="/characters/*" element={<CharactersRoutes />} />
      <Route path="/locations/*" element={<LocationsRoutes />} />
    </Routes>,
    { route },
  )
}
