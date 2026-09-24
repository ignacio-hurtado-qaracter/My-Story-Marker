// The table of contents and the reading order, as pure functions. Spec 002, FR-SCN-01, FR-SCN-03,
// FR-SCN-04; plan decision P11.
//
// The chapters are authoritative for reading order: a chapter orders its scenes
// (docs/domain-knowledge.md Figure 1). `GET /scenes` only finds the scenes no chapter lists.
import type { Schemas } from '../shared/api'

type Chapter = Schemas['Chapter']

export interface TocChapter {
  id: string
  function: string
  /** The chapter's scenes, in the chapter's (discourse) order. */
  scenes: string[]
}

export interface Toc {
  /** In file order. */
  chapters: TocChapter[]
  /** Scenes no chapter lists, sorted by id: no discourse order is known for them. */
  unassigned: string[]
}

export interface Neighbours {
  previous?: string
  next?: string
}

/**
 * Build the table of contents. Every scene appears exactly once:
 * - a scene listed twice (by one chapter or by two) stays at its first place and is dropped later;
 * - a scene a chapter lists that `GET /scenes` did not return is kept, because the chapter is
 *   authoritative for reading order (its page then shows not-found, which is the truth);
 * - a scene no chapter lists goes to `unassigned`, sorted by id, whatever order `sceneIds` has.
 */
export function buildToc(chapters: readonly Chapter[], sceneIds: readonly string[]): Toc {
  const placed = new Set<string>()
  const tocChapters = chapters.map((chapter) => {
    const scenes: string[] = []
    for (const id of chapter.scenes ?? []) {
      if (!placed.has(id)) {
        placed.add(id)
        scenes.push(id)
      }
    }
    return { id: chapter.id, function: chapter.function, scenes }
  })
  const unassigned = [...new Set(sceneIds)].filter((id) => !placed.has(id)).sort()
  return { chapters: tocChapters, unassigned }
}

/** The reading order: every chapter's scenes in file order, then the unassigned scenes. */
export function flatten(toc: Toc): string[] {
  return [...toc.chapters.flatMap((chapter) => chapter.scenes), ...toc.unassigned]
}

/** Previous and next scene in the reading order; empty for a scene the order does not contain. */
export function neighbours(toc: Toc, id: string): Neighbours {
  const order = flatten(toc)
  const index = order.indexOf(id)
  if (index === -1) {
    return {}
  }
  const previous = order[index - 1]
  const next = order[index + 1]
  return {
    ...(previous === undefined ? {} : { previous }),
    ...(next === undefined ? {} : { next }),
  }
}
