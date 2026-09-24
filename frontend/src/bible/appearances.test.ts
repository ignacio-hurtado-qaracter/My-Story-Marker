// The appearances functions of FR-BIBLE-01: examples on the fixture's story, then fast-check
// properties. Spec 003, AC 16; plan decisions Q12 and Q13.
import fc from 'fast-check'
import { describe, expect, it } from 'vitest'

import type { Schemas } from '../shared/api'
import {
  characterAppearances,
  chapterCount,
  isDescendant,
  locationAppearances,
  parentMap,
  sublocations,
  type AppearanceGroup,
} from './appearances'
import { CHAPTERS, LOCATIONS, SCENES, scene } from './testing'

type Chapter = Schemas['Chapter']
type Scene = Schemas['Scene']

function chapter(id: string, scenes: string[], fn = `función de ${id}`): Chapter {
  return { id, function: fn, arc: 'ar_test', budget: 1000, target_tension_in: 1, target_tension_out: 2, scenes }
}

/** The groups as `[chapterId, [sceneId, role-or-via]...]`, easy to read in an assertion. */
function summary<S extends { sceneId: string }>(groups: AppearanceGroup<S>[], field: (scene: S) => string | null) {
  return groups.map((group) => [group.chapterId, group.scenes.map((s) => `${s.sceneId}:${String(field(s))}`)])
}

describe('characterAppearances', () => {
  // spec 003 / AC 16
  it('lists the scenes a character is the POV of, by chapter, in reading order', () => {
    const groups = characterAppearances('vance', CHAPTERS, SCENES)
    expect(summary(groups, (s) => s.role)).toEqual([
      ['ch01', ['001:pov', '003:pov']],
      ['ch02', ['004:pov', '005:participant', '006:pov']],
    ])
  })

  // spec 003 / AC 16
  it('marks a participant as present and leaves out the chapters where the character is absent', () => {
    expect(summary(characterAppearances('quiej', CHAPTERS, SCENES), (s) => s.role)).toEqual([
      ['ch01', ['001:participant', '002:participant']],
      ['ch02', ['005:pov']],
    ])
    expect(characterAppearances('nobody', CHAPTERS, SCENES)).toEqual([])
  })

  // spec 003 / AC 16 (Q13)
  it('carries the chapter number and the display title, straight or curly quotes, else null', () => {
    const [first, second] = characterAppearances('vance', CHAPTERS, SCENES)
    expect(first).toMatchObject({ chapterId: 'ch01', chapterNumber: 1, chapterTitle: 'The Sealed Half' })
    expect(second).toMatchObject({ chapterId: 'ch02', chapterNumber: 2, chapterTitle: 'The Calving Window' })
    const untitled = characterAppearances('vance', [chapter('ch09', ['001'], 'Vance loses the key.')], SCENES)
    expect(untitled[0]).toMatchObject({ chapterId: 'ch09', chapterNumber: 1, chapterTitle: null })
  })

  // spec 003 / AC 16
  it('groups scenes no chapter lists under "Sin capítulo", last and sorted by id', () => {
    const scenes = [...SCENES, scene('009', 'vance', [], 'pump_vault'), scene('007', 'ilan', ['vance'], 'pump_vault')]
    const groups = characterAppearances('vance', CHAPTERS, scenes)
    expect(groups.at(-1)).toEqual({
      chapterId: null,
      chapterNumber: null,
      chapterTitle: null,
      scenes: [
        { sceneId: '007', role: 'participant' },
        { sceneId: '009', role: 'pov' },
      ],
    })
    expect(chapterCount(groups)).toBe(2)
  })

  // spec 003 / AC 16
  it('keeps a scene listed twice at its first place and skips a listed scene with no record', () => {
    const chapters = [chapter('ch01', ['003', '001', '003']), chapter('ch02', ['001', '404', '004'])]
    expect(summary(characterAppearances('vance', chapters, SCENES), (s) => s.role)).toEqual([
      ['ch01', ['003:pov', '001:pov']],
      ['ch02', ['004:pov']],
      [null, ['005:participant', '006:pov']],
    ])
  })
})

describe('locationAppearances', () => {
  // spec 003 / AC 16
  it('counts scenes set in a sublocation, marked via that sublocation', () => {
    const groups = locationAppearances('kestrel_deep', CHAPTERS, SCENES, LOCATIONS)
    expect(summary(groups, (s) => s.via)).toEqual([
      ['ch01', ['001:null', '002:pump_vault', '003:pump_vault']],
      ['ch02', ['004:pump_vault', '005:null', '006:pump_vault']],
    ])
  })

  // spec 003 / AC 16
  it('counts only direct scenes for a leaf, never the scenes of its parent', () => {
    const groups = locationAppearances('pump_vault', CHAPTERS, SCENES, LOCATIONS)
    expect(summary(groups, (s) => s.via)).toEqual([
      ['ch01', ['002:null', '003:null']],
      ['ch02', ['004:null', '006:null']],
    ])
  })

  // spec 003 / AC 16
  it('follows a deeper chain and survives a cycle in the parent data', () => {
    const tree = [
      { id: 'root', parent: null },
      { id: 'mid', parent: 'root' },
      { id: 'leaf', parent: 'mid' },
      { id: 'loop_a', parent: 'loop_b' },
      { id: 'loop_b', parent: 'loop_a' },
    ]
    const scenes = [scene('001', 'x', [], 'leaf'), scene('002', 'x', [], 'loop_a')]
    expect(summary(locationAppearances('root', [], scenes, tree), (s) => s.via)).toEqual([[null, ['001:leaf']]])
    expect(locationAppearances('elsewhere', [], scenes, tree)).toEqual([])
    expect(isDescendant('loop_a', 'root', parentMap(tree))).toBe(false)
  })
})

describe('sublocations', () => {
  // spec 003 / AC 16
  it('lists the direct children, sorted, and none for a leaf', () => {
    const tree = [...LOCATIONS, { id: 'a_hatch', parent: 'kestrel_deep' }, { id: 'z_deeper', parent: 'pump_vault' }]
    expect(sublocations('kestrel_deep', tree)).toEqual(['a_hatch', 'pump_vault'])
    expect(sublocations('z_deeper', tree)).toEqual([])
  })
})

// ---------- Properties ----------

const CAST = ['ana', 'ben', 'cai', 'dua'] as const
const PLACES = ['l0', 'l1', 'l2', 'l3', 'l4'] as const
const SCENE_POOL = Array.from({ length: 12 }, (_, index) => String(index + 1).padStart(3, '0'))

/** An acyclic location tree: each place's parent is an earlier place or none. */
const treeArb = fc
  .tuple(...PLACES.map((_, index) => fc.integer({ min: -1, max: index - 1 })))
  .map((parents) =>
    PLACES.map((id, index) => {
      const parent = parents.at(index) ?? -1
      return { id, parent: parent < 0 ? null : (PLACES.at(parent) ?? null) }
    }),
  )

const scenesArb = fc.uniqueArray(fc.constantFrom(...SCENE_POOL), { maxLength: SCENE_POOL.length }).chain((ids) =>
  fc.tuple(
    ...ids.map((id) =>
      fc
        .record({
          pov: fc.constantFrom(...CAST),
          present: fc.subarray([...CAST]),
          location: fc.constantFrom(...PLACES),
        })
        .map(({ pov, present, location }) =>
          scene(
            id,
            pov,
            present.filter((name) => name !== pov),
            location,
          ),
        ),
    ),
  ),
)

const chaptersArb = fc
  .array(fc.array(fc.constantFrom(...SCENE_POOL), { maxLength: 6 }), { maxLength: 4 })
  .map((lists) => lists.map((ids, index) => chapter(`ch${String(index + 1)}`, ids)))

/** The reading order, stated independently: chapters' first listings, then the rest by id. */
function readingOrder(chapters: Chapter[], scenes: Scene[]): string[] {
  const exists = new Set(scenes.map((s) => s.id))
  const seen = new Set<string>()
  const order: string[] = []
  for (const c of chapters) {
    for (const id of c.scenes ?? []) {
      if (exists.has(id) && !seen.has(id)) {
        seen.add(id)
        order.push(id)
      }
    }
  }
  return [...order, ...[...exists].filter((id) => !seen.has(id)).sort()]
}

/** The chapter a scene is read in: the first that lists it, else none. */
function homeChapter(chapters: Chapter[], id: string): string | null {
  return chapters.find((c) => (c.scenes ?? []).includes(id))?.id ?? null
}

function ancestorsOf(id: string, tree: { id: string; parent: string | null }[]): string[] {
  const out: string[] = []
  let current = tree.find((l) => l.id === id)?.parent ?? null
  while (current !== null) {
    out.push(current)
    const here: string = current
    current = tree.find((l) => l.id === here)?.parent ?? null
  }
  return out
}

/** Shared checks: reading order, grouping by home chapter, no scene twice, no empty group. */
function checkShape<S extends { sceneId: string }>(groups: AppearanceGroup<S>[], chapters: Chapter[], scenes: Scene[]) {
  const ids = groups.flatMap((g) => g.scenes.map((s) => s.sceneId))
  expect(new Set(ids).size).toBe(ids.length)
  const order = readingOrder(chapters, scenes)
  expect(ids).toEqual(order.filter((id) => ids.includes(id)))
  for (const group of groups) {
    expect(group.scenes.length).toBeGreaterThan(0)
    for (const s of group.scenes) {
      expect(homeChapter(chapters, s.sceneId)).toBe(group.chapterId)
    }
    if (group.chapterId !== null) {
      expect(chapters[(group.chapterNumber ?? 0) - 1]?.id).toBe(group.chapterId)
    }
  }
  const numbers = groups.map((g) => g.chapterNumber ?? Number.POSITIVE_INFINITY)
  expect(numbers).toEqual([...numbers].sort((a, b) => a - b))
  expect(new Set(numbers).size).toBe(numbers.length)
}

describe('appearances properties', () => {
  // spec 003 / AC 16
  it('character: every scene has the character present, all such scenes appear, in reading order, once', () => {
    fc.assert(
      fc.property(fc.constantFrom(...CAST), chaptersArb, scenesArb, (who, chapters, scenes) => {
        const groups = characterAppearances(who, chapters, scenes)
        const byId = new Map(scenes.map((s) => [s.id, s]))
        for (const s of groups.flatMap((g) => g.scenes)) {
          const record = byId.get(s.sceneId)
          expect(record).toBeDefined()
          if (s.role === 'pov') expect(record?.pov).toBe(who)
          else expect(record?.participants).toContain(who)
        }
        const expected = scenes.filter((s) => s.pov === who || s.participants.includes(who)).map((s) => s.id)
        expect(groups.flatMap((g) => g.scenes.map((s) => s.sceneId)).sort()).toEqual(expected.sort())
        checkShape(groups, chapters, scenes)
      }),
    )
  })

  // spec 003 / AC 16
  it('location: every scene is set in it or below it (via its own place), all appear, in reading order, once', () => {
    fc.assert(
      fc.property(fc.constantFrom(...PLACES), chaptersArb, scenesArb, treeArb, (place, chapters, scenes, tree) => {
        const groups = locationAppearances(place, chapters, scenes, tree)
        const byId = new Map(scenes.map((s) => [s.id, s]))
        for (const s of groups.flatMap((g) => g.scenes)) {
          const record = byId.get(s.sceneId)
          expect(record).toBeDefined()
          if (s.via === null) {
            expect(record?.location).toBe(place)
          } else {
            expect(record?.location).toBe(s.via)
            expect(ancestorsOf(s.via, tree)).toContain(place)
          }
        }
        const expected = scenes
          .filter((s) => s.location === place || ancestorsOf(s.location, tree).includes(place))
          .map((s) => s.id)
        expect(groups.flatMap((g) => g.scenes.map((s) => s.sceneId)).sort()).toEqual(expected.sort())
        checkShape(groups, chapters, scenes)
      }),
    )
  })
})
