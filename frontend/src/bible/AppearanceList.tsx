// "Aparece en": where a character or a location appears, by chapter, each chapter and scene a link
// into the reader. Spec 003, FR-BIBLE-01, FR-BIBLE-03..05. (Plan 003 names this file
// `Appearances.tsx`; it is `AppearanceList.tsx` because `./Appearances` and `./appearances` are the
// same path on case-insensitive file systems, and the pure `appearances.ts` would be imported.)
import './bible.css'

import { useId } from 'react'
import { Link } from 'react-router'

import type { Loadable } from './api'
import { chapterCount, type AppearanceGroup } from './appearances'
import { plural } from './names'

/** One scene of an appearance, with what the sheet says about it ("punto de vista", "vía …"). */
export interface AppearanceItem {
  sceneId: string
  note: string
}

export type AppearanceGroups = AppearanceGroup<AppearanceItem>[]

/** FR-BIBLE-05: what a sheet or a list shows when scene records fail. */
export const APPEARANCES_FAILED = 'No se han podido calcular las apariciones'

/** Where a scene of a group is read: its anchor in the chapter reader, or its own page. */
function sceneHref(chapterId: string | null, sceneId: string): string {
  return chapterId === null ? `/scenes/${sceneId}` : `/chapters/${chapterId}#scene-${sceneId}`
}

export interface AppearancesProps {
  appearances: Loadable<AppearanceGroups>
  /** Shown when the entity appears in no scene. */
  emptyText: string
}

export function Appearances({ appearances, emptyText }: AppearancesProps) {
  const headingId = useId()
  return (
    <section className="bible-appearances card" aria-labelledby={headingId}>
      <h2 id={headingId} className="bible-section-title">
        Aparece en
      </h2>
      <AppearancesBody appearances={appearances} emptyText={emptyText} />
    </section>
  )
}

function AppearancesBody({ appearances, emptyText }: AppearancesProps) {
  if (appearances.status === 'pending') {
    return (
      <p role="status" className="bible-note">
        Calculando apariciones…
      </p>
    )
  }
  if (appearances.status === 'error') {
    return <p className="bible-note">{APPEARANCES_FAILED}</p>
  }
  if (appearances.data.length === 0) {
    return <p className="bible-note">{emptyText}</p>
  }
  return (
    <ol className="bible-appearance-list">
      {appearances.data.map((group) => (
        <AppearanceChapter key={group.chapterId ?? '(sin capítulo)'} group={group} />
      ))}
    </ol>
  )
}

function AppearanceChapter({ group }: { group: AppearanceGroup<AppearanceItem> }) {
  const { chapterId, chapterNumber, chapterTitle } = group
  return (
    <li className="bible-appearance">
      {chapterId === null || chapterNumber === null ? (
        <p className="bible-appearance-chapter">
          <span className="bible-appearance-number">Sin capítulo</span>
        </p>
      ) : (
        <Link to={`/chapters/${chapterId}`} className="bible-appearance-chapter">
          <span className="bible-appearance-number">{`Capítulo ${String(chapterNumber)}`}</span>
          {chapterTitle === null ? null : (
            <>
              {' '}
              <span className="bible-appearance-title">{chapterTitle}</span>
            </>
          )}
        </Link>
      )}
      <ul className="bible-chip-list">
        {group.scenes.map((scene) => (
          <li key={scene.sceneId}>
            <Link to={sceneHref(chapterId, scene.sceneId)} className="bible-chip">
              {/* The separator stays in the text node: an element's own text is trimmed when the
                  accessible name is computed, and the name must read "Escena 001 · presente". */}
              {`Escena ${scene.sceneId} · `}
              <span className="bible-chip-note">{scene.note}</span>
            </Link>
          </li>
        ))}
      </ul>
    </li>
  )
}

export interface ChapterChipsProps {
  /** `null` while the appearances load or when they failed: no chips. */
  groups: readonly AppearanceGroup<unknown>[] | null
}

/** FR-BIBLE-02: a card's "Aparece en" chips, one per chapter, each a link into the reader. */
export function ChapterChips({ groups }: ChapterChipsProps) {
  if (groups === null) {
    return null
  }
  const chapters = groups.flatMap((group) =>
    group.chapterId === null || group.chapterNumber === null ? [] : [{ id: group.chapterId, number: group.chapterNumber }],
  )
  if (chapters.length === 0) {
    return <p className="bible-chips bible-note">Aún no aparece en ningún capítulo</p>
  }
  return (
    <div className="bible-chips">
      <span className="bible-label">Aparece en</span>
      <ul className="bible-chip-list">
        {chapters.map((chapter) => (
          <li key={chapter.id}>
            <Link to={`/chapters/${chapter.id}`} className="bible-chip">
              {`Capítulo ${String(chapter.number)}`}
            </Link>
          </li>
        ))}
      </ul>
    </div>
  )
}

/** A sheet head's pill: in how many chapters the entity appears, once that is known. */
export function AppearancePill({ appearances }: { appearances: Loadable<AppearanceGroups> }) {
  if (appearances.status !== 'success') {
    return null
  }
  const chapters = chapterCount(appearances.data)
  return chapters === 0 ? (
    <span className="pill pill-neutral">Aún no aparece en ningún capítulo</span>
  ) : (
    <span className="pill">{`Aparece en ${plural(chapters, 'capítulo', 'capítulos')}`}</span>
  )
}
