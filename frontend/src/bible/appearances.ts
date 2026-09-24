// Where a character or a location appears, as pure functions of the chapters and the scene
// records. Spec 003, FR-BIBLE-01, AC 16; spec decision R2-5; plan decision Q12.
//
// Reading order is the chapters' (docs/domain-knowledge.md Figure 1): chapters in file order, each
// chapter's scenes in its own (discourse) order. A scene listed twice stays at its first place; a
// scene no chapter lists goes to a last "Sin capítulo" group, sorted by id. Only scenes with a
// record can be placed: a chapter entry with no record is skipped, because nothing says who or
// where it is.
import type { Schemas } from '../shared/api'
import { chapterDisplayTitle } from './names'

type Chapter = Pick<Schemas['Chapter'], 'id' | 'function' | 'scenes'>
type Scene = Pick<Schemas['Scene'], 'id' | 'pov' | 'participants' | 'location'>
type Location = Pick<Schemas['Location'], 'id' | 'parent'>

/** "punto de vista" when the character is the scene's POV, "presente" when a participant. */
export type CharacterRole = 'pov' | 'participant'

export interface CharacterScene {
  sceneId: string
  role: CharacterRole
}

export interface LocationScene {
  sceneId: string
  /** `null` when the scene is set in the location itself; else the scene's own location, a descendant. */
  via: string | null
}

export interface AppearanceGroup<S> {
  /** `null` for the scenes no chapter lists ("Sin capítulo"). */
  chapterId: string | null
  /** 1-based position in file order; `null` for "Sin capítulo". */
  chapterNumber: number | null
  /** The display title (R2-4), or `null`: the UI then shows "Capítulo N". */
  chapterTitle: string | null
  /** Never empty: a group with no appearance is left out. */
  scenes: S[]
}

function byId(a: Scene, b: Scene): number {
  if (a.id < b.id) return -1
  return a.id > b.id ? 1 : 0
}

/** Every scene with a record, once, grouped by chapter in reading order. */
function readingGroups(chapters: readonly Chapter[], scenes: readonly Scene[]): AppearanceGroup<Scene>[] {
  const records = new Map(scenes.map((scene) => [scene.id, scene]))
  const placed = new Set<string>()
  const groups = chapters.map((chapter, index): AppearanceGroup<Scene> => {
    const inChapter: Scene[] = []
    for (const id of chapter.scenes ?? []) {
      const scene = records.get(id)
      if (scene !== undefined && !placed.has(id)) {
        placed.add(id)
        inChapter.push(scene)
      }
    }
    return {
      chapterId: chapter.id,
      chapterNumber: index + 1,
      chapterTitle: chapterDisplayTitle(chapter.function),
      scenes: inChapter,
    }
  })
  const unlisted = [...records.values()].filter((scene) => !placed.has(scene.id)).sort(byId)
  groups.push({ chapterId: null, chapterNumber: null, chapterTitle: null, scenes: unlisted })
  return groups
}

/** Keep, in each group, the scenes `pick` maps to an appearance; drop the groups left empty. */
function collect<S>(groups: AppearanceGroup<Scene>[], pick: (scene: Scene) => S | null): AppearanceGroup<S>[] {
  return groups.flatMap((group) => {
    const hits = group.scenes.flatMap((scene) => {
      const hit = pick(scene)
      return hit === null ? [] : [hit]
    })
    return hits.length === 0 ? [] : [{ ...group, scenes: hits }]
  })
}

/** FR-BIBLE-01: the scenes a character is the POV of, or present in, by chapter. */
export function characterAppearances(
  characterId: string,
  chapters: readonly Chapter[],
  scenes: readonly Scene[],
): AppearanceGroup<CharacterScene>[] {
  return collect(readingGroups(chapters, scenes), (scene): CharacterScene | null => {
    if (scene.pov === characterId) return { sceneId: scene.id, role: 'pov' }
    if (scene.participants.includes(characterId)) return { sceneId: scene.id, role: 'participant' }
    return null
  })
}

/** The parent of each location; a missing `parent` is a root. */
export function parentMap(locations: readonly Location[]): Map<string, string | null> {
  return new Map(locations.map((location) => [location.id, location.parent ?? null]))
}

/** Whether `ancestor` is on the parent chain above `id`. A cycle in the data ends the walk. */
export function isDescendant(id: string, ancestor: string, parents: ReadonlyMap<string, string | null>): boolean {
  const seen = new Set<string>([id])
  let current = parents.get(id) ?? null
  while (current !== null && !seen.has(current)) {
    if (current === ancestor) return true
    seen.add(current)
    current = parents.get(current) ?? null
  }
  return false
}

/**
 * FR-BIBLE-01: the scenes set in a location (direct) or in one of its descendants in the `parent`
 * tree (via that sublocation), by chapter.
 */
export function locationAppearances(
  locationId: string,
  chapters: readonly Chapter[],
  scenes: readonly Scene[],
  locations: readonly Location[],
): AppearanceGroup<LocationScene>[] {
  const parents = parentMap(locations)
  return collect(readingGroups(chapters, scenes), (scene): LocationScene | null => {
    if (scene.location === locationId) return { sceneId: scene.id, via: null }
    return isDescendant(scene.location, locationId, parents) ? { sceneId: scene.id, via: scene.location } : null
  })
}

/** The direct children of a location, sorted by id. */
export function sublocations(locationId: string, locations: readonly Location[]): string[] {
  return locations
    .filter((location) => location.parent === locationId && location.id !== locationId)
    .map((location) => location.id)
    .sort()
}

/** How many chapters (not counting "Sin capítulo") the groups span. */
export function chapterCount<S>(groups: readonly AppearanceGroup<S>[]): number {
  return groups.filter((group) => group.chapterId !== null).length
}
