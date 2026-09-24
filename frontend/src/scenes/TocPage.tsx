// `/scenes`: the chapter index. Spec 002, FR-SCN route table, FR-SCN-01, AC 8; spec 003,
// FR-INDEX-01/02, AC 14 (revision 2: titled "Índice", numbered chapter cards in main's
// book-card style, each with its display title, "Leer capítulo" and its scene chips).
import './scenes.css'

import { Link } from 'react-router'

import { ErrorPanel, Heading } from '../shared/ui'
import { describeError } from './api'
import { chapterSummary, chapterTitle } from './chapterTitle'
import { Skeleton } from './Skeleton'
import { flatten, type Toc, type TocChapter } from './toc'
import { useToc } from './useToc'

export function TocPage() {
  const { data, error, isPending, refetch } = useToc()
  let body
  // The count pills exist only once the index has loaded.
  let counts = null
  if (isPending) {
    body = <Skeleton lines={6} />
  } else if (error !== null) {
    body = (
      <ErrorPanel
        message={describeError(error)}
        onRetry={() => {
          void refetch()
        }}
      />
    )
  } else {
    counts = <TocCounts toc={data} />
    body =
      data.chapters.length === 0 && data.unassigned.length === 0 ? (
        <p className="scenes-empty">Todavía no hay escenas</p>
      ) : (
        <TocList toc={data} />
      )
  }
  return (
    <div className="toc-page">
      <title>Índice · My Story Marker</title>
      <section className="toc-head">
        <p className="eyebrow">Novela</p>
        <Heading>Índice</Heading>
        <p className="toc-lead">
          Los capítulos en orden de lectura. Abre uno para leerlo de principio a fin, o salta directamente a una
          escena.
        </p>
        {counts}
      </section>
      {body}
    </div>
  )
}

function plural(count: number, one: string, many: string): string {
  return `${String(count)} ${count === 1 ? one : many}`
}

function TocCounts({ toc }: { toc: Toc }) {
  return (
    <div className="toc-counts">
      <span className="pill">{plural(toc.chapters.length, 'capítulo', 'capítulos')}</span>
      <span className="pill pill-neutral">{plural(flatten(toc).length, 'escena', 'escenas')}</span>
    </div>
  )
}

function TocList({ toc }: { toc: Toc }) {
  return (
    <div className="toc-chapters">
      {toc.chapters.map((chapter, index) => (
        <ChapterCard key={chapter.id} chapter={chapter} number={index + 1} />
      ))}
      {toc.unassigned.length === 0 ? null : (
        <section className="toc-chapter toc-chapter-loose card">
          <div className="toc-chapter-cover" aria-hidden="true" />
          <div className="toc-chapter-body">
            <Heading level={2}>Sin capítulo</Heading>
            <p className="toc-chapter-function">Escenas que todavía no pertenecen a ningún capítulo.</p>
            <SceneLinks ids={toc.unassigned} />
            <div className="toc-chapter-footer">
              <span className="toc-chapter-count">{plural(toc.unassigned.length, 'escena', 'escenas')}</span>
            </div>
          </div>
        </section>
      )}
    </div>
  )
}

/**
 * One numbered chapter. The eyebrow "Capítulo N" is shown only when the chapter has a title of
 * its own; otherwise the heading already reads "Capítulo N". The chapter id stays inside the
 * heading, as a small label: spec 002's tests find a chapter by it.
 */
function ChapterCard({ chapter, number }: { chapter: TocChapter; number: number }) {
  const title = chapterTitle(chapter.function)
  const summary = chapterSummary(chapter.function)
  return (
    <section className="toc-chapter card">
      <div className="toc-chapter-cover" aria-hidden="true">
        <span className="toc-chapter-numeral">{String(number).padStart(2, '0')}</span>
      </div>
      <div className="toc-chapter-body">
        {title === null ? null : <p className="eyebrow">Capítulo {number}</p>}
        <Heading level={2}>
          <span className="toc-chapter-name">{title ?? `Capítulo ${String(number)}`}</span>{' '}
          <span className="toc-chapter-id">{chapter.id}</span>
        </Heading>
        {summary === '' ? null : <p className="toc-chapter-function">{summary}</p>}
        <SceneLinks ids={chapter.scenes} />
        <div className="toc-chapter-footer">
          <span className="toc-chapter-count">{plural(chapter.scenes.length, 'escena', 'escenas')}</span>
          <Link to={`/chapters/${chapter.id}`} className="scenes-cta">
            Leer capítulo
          </Link>
        </div>
      </div>
    </section>
  )
}

function SceneLinks({ ids }: { ids: string[] }) {
  if (ids.length === 0) {
    return null
  }
  return (
    <ol className="scene-chips">
      {ids.map((id) => (
        <li key={id}>
          <Link to={`/scenes/${id}`} className="scene-chip">
            Escena {id}
          </Link>
        </li>
      ))}
    </ol>
  )
}
