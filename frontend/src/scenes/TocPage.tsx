// `/scenes`: the table of contents, by chapter. Spec 002, FR-SCN route table, FR-SCN-01, AC 8.
import { Link } from 'react-router'

import { ErrorPanel, Heading } from '../shared/ui'
import { describeError } from './api'
import { Skeleton } from './Skeleton'
import type { Toc } from './toc'
import { useToc } from './useToc'

// WCAG 2.2 AA 2.5.8: stacked scene links need a 24 px target (spec 002, NFR-02, AC 11).
const TARGET = { display: 'inline-block', minHeight: '24px', padding: '4px 0' } as const

export function TocPage() {
  const { data, error, isPending, refetch } = useToc()
  let body
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
  } else if (data.chapters.length === 0 && data.unassigned.length === 0) {
    body = <p>Todavía no hay escenas</p>
  } else {
    body = <TocList toc={data} />
  }
  return (
    <section>
      <title>Escenas · My Story Marker</title>
      <Heading>Escenas</Heading>
      {body}
    </section>
  )
}

function TocList({ toc }: { toc: Toc }) {
  return (
    <>
      {toc.chapters.map((chapter) => (
        <section key={chapter.id} className="toc-chapter">
          <Heading level={2}>{chapter.id}</Heading>
          <p>{chapter.function}</p>
          <SceneLinks ids={chapter.scenes} />
        </section>
      ))}
      {toc.unassigned.length === 0 ? null : (
        <section className="toc-chapter">
          <Heading level={2}>Sin capítulo</Heading>
          <SceneLinks ids={toc.unassigned} />
        </section>
      )}
    </>
  )
}

function SceneLinks({ ids }: { ids: string[] }) {
  return (
    <ol>
      {ids.map((id) => (
        <li key={id}>
          <Link to={`/scenes/${id}`} style={TARGET}>
            Escena {id}
          </Link>
        </li>
      ))}
    </ol>
  )
}
