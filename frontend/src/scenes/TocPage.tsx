// `/scenes`: the table of contents, by chapter. Spec 002, FR-SCN route table, FR-SCN-01, AC 8.
// Spec 003: the book header card (FR-BOOK) and the chapter cards with scene chips (FR-SCN3-01).
import './scenes.css'

import { Link } from 'react-router'

import { ErrorPanel, Heading } from '../shared/ui'
import { describeError } from './api'
import { BookHeader } from './BookHeader'
import { Skeleton } from './Skeleton'
import { flatten, type Toc } from './toc'
import { useToc } from './useToc'

export function TocPage() {
  const { data, error, isPending, refetch } = useToc()
  let body
  // FR-BOOK-03: the count pills exist only once the table of contents has loaded.
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
    <section>
      <title>Escenas · My Story Marker</title>
      {/* FR-BOOK-01: a section, never a <header>, with no h2 and no link inside. */}
      <section className="book-header card">
        <p className="eyebrow">Novela</p>
        <Heading>Escenas</Heading>
        <BookHeader />
        {counts}
      </section>
      {body}
    </section>
  )
}

function plural(count: number, one: string, many: string): string {
  return `${String(count)} ${count === 1 ? one : many}`
}

function TocCounts({ toc }: { toc: Toc }) {
  return (
    <div className="book-counts">
      <span className="pill">{plural(toc.chapters.length, 'capítulo', 'capítulos')}</span>
      <span className="pill pill-neutral">{plural(flatten(toc).length, 'escena', 'escenas')}</span>
    </div>
  )
}

function TocList({ toc }: { toc: Toc }) {
  return (
    <div className="toc-chapters">
      {toc.chapters.map((chapter) => (
        <section key={chapter.id} className="toc-chapter card">
          <Heading level={2}>{chapter.id}</Heading>
          <p className="toc-chapter-function">{chapter.function}</p>
          <SceneLinks ids={chapter.scenes} />
        </section>
      ))}
      {toc.unassigned.length === 0 ? null : (
        <section className="toc-chapter card">
          <Heading level={2}>Sin capítulo</Heading>
          <SceneLinks ids={toc.unassigned} />
        </section>
      )}
    </div>
  )
}

function SceneLinks({ ids }: { ids: string[] }) {
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
