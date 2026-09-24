// `/chapters/:id`: the chapter reader. Spec 003, FR-READ-01/02/03, AC 15; plan 003 Q8, Q13.
//
// The chapter list comes from the index's own query (useToc), so moving between the index, the
// reader and a scene reuses one cache. Each scene's draft is its own query (the same key as
// ScenePage's), so one missing or failing draft never blocks the others.
import './scenes.css'

import { useQueries, type UseQueryResult } from '@tanstack/react-query'
import { useEffect } from 'react'
import { Link, useLocation, useParams } from 'react-router'

import type { Schemas } from '../shared/api'
import { ErrorPanel, Heading, Prose } from '../shared/ui'
import { describeError, fetchDraft, isSceneId } from './api'
import { chapterSummary, chapterTitle, displayTitle } from './chapterTitle'
import { Skeleton } from './Skeleton'
import type { TocChapter } from './toc'
import { useToc } from './useToc'

type DraftQuery = UseQueryResult<Schemas['Draft'] | null>

export function ChapterPage() {
  const { id = '' } = useParams()
  const { data, error, isPending, refetch } = useToc()

  if (isPending) {
    return (
      <div className="chapter-state">
        <title>Capítulo · My Story Marker</title>
        <Skeleton lines={8} />
      </div>
    )
  }
  if (error !== null) {
    return (
      <div className="chapter-state">
        <title>Capítulo · My Story Marker</title>
        <Heading>No se pudo cargar el capítulo</Heading>
        <ErrorPanel
          message={describeError(error)}
          onRetry={() => {
            void refetch()
          }}
        />
      </div>
    )
  }
  const chapter = data.chapters.find((candidate) => candidate.id === id)
  if (chapter === undefined) {
    return <ChapterNotFound />
  }
  const index = data.chapters.indexOf(chapter)
  // Keyed by chapter: previous / next mount a fresh reader, which starts at the top.
  return <ChapterReader key={chapter.id} chapters={data.chapters} chapter={chapter} index={index} />
}

function ChapterNotFound() {
  return (
    <section className="scenes-panel">
      <title>Capítulo no encontrado · My Story Marker</title>
      <Heading>Capítulo no encontrado</Heading>
      <p>No existe ningún capítulo con ese identificador.</p>
      <Link to="/scenes" className="btn-ghost">
        Volver al índice
      </Link>
    </section>
  )
}

interface ChapterReaderProps {
  chapters: TocChapter[]
  chapter: TocChapter
  /** The chapter's 0-based position in file order. */
  index: number
}

function ChapterReader({ chapters, chapter, index }: ChapterReaderProps) {
  const number = index + 1
  const ownTitle = chapterTitle(chapter.function)
  const title = displayTitle(chapter.function, number)
  const summary = chapterSummary(chapter.function)

  const drafts = useQueries({
    queries: chapter.scenes.map((sceneId) => ({
      queryKey: ['scenes', 'draft', sceneId],
      queryFn: () => fetchDraft(sceneId),
      // FR-SCN-06: an id the backend would refuse is never sent; its section says so.
      enabled: isSceneId(sceneId),
    })),
  })
  const settled = chapter.scenes.every((sceneId, i) => !isSceneId(sceneId) || drafts.at(i)?.isPending === false)
  useArrivalScroll(settled)

  const words = drafts.reduce((total, draft) => total + (draft.data?.words ?? 0), 0)
  const previous = chapters[index - 1]
  const next = chapters[index + 1]

  return (
    <div className="chapter-layout">
      <title>{`${ownTitle === null ? title : `Capítulo ${String(number)} · ${title}`} · My Story Marker`}</title>
      <article className="chapter-reading">
        <div className="chapter-head">
          {ownTitle === null ? null : <p className="eyebrow">Capítulo {number}</p>}
          <Heading>{title}</Heading>
          {summary === '' ? null : <p className="chapter-summary">{summary}</p>}
          <p className="chapter-pills">
            <span className="pill pill-neutral">
              {chapter.scenes.length === 1 ? '1 escena' : `${String(chapter.scenes.length)} escenas`}
            </span>
            {settled && words > 0 ? <span className="pill">{words} palabras</span> : null}
          </p>
        </div>

        {chapter.scenes.length === 0 ? (
          <p className="scenes-empty">Este capítulo todavía no tiene escenas</p>
        ) : (
          chapter.scenes.map((sceneId, i) => <SceneSection key={sceneId} id={sceneId} draft={drafts.at(i)} />)
        )}

        {previous === undefined && next === undefined ? null : (
          <nav aria-label="Capítulos vecinos" className="chapter-nav">
            {previous === undefined ? null : (
              <Link to={`/chapters/${previous.id}`} rel="prev" className="btn-ghost chapter-nav-link">
                <span className="chapter-nav-label">
                  <span aria-hidden="true">← </span>Capítulo anterior<span className="visually-hidden">:</span>
                </span>{' '}
                <span className="chapter-nav-title">{displayTitle(previous.function, number - 1)}</span>
              </Link>
            )}
            {next === undefined ? null : (
              <Link to={`/chapters/${next.id}`} rel="next" className="scenes-cta chapter-nav-link chapter-nav-next">
                <span className="chapter-nav-label">
                  Capítulo siguiente<span className="visually-hidden">:</span>
                  <span aria-hidden="true"> →</span>
                </span>{' '}
                <span className="chapter-nav-title">{displayTitle(next.function, number + 1)}</span>
              </Link>
            )}
          </nav>
        )}
      </article>
      <ChapterIndex chapters={chapters} current={index} />
    </div>
  )
}

/** One scene of the chapter: its heading, then its prose or the reason there is none. */
function SceneSection({ id, draft }: { id: string; draft: DraftQuery | undefined }) {
  const headingId = `scene-${id}-title`
  let body
  if (!isSceneId(id) || draft === undefined) {
    body = <p className="chapter-scene-empty">Esta escena tiene un identificador no válido</p>
  } else if (draft.isPending) {
    body = <Skeleton lines={4} />
  } else if (draft.error !== null) {
    body = (
      <div className="chapter-scene-error">
        <p>No se pudo cargar esta escena: {describeError(draft.error)}</p>
        <button
          type="button"
          className="btn-ghost"
          onClick={() => {
            void draft.refetch()
          }}
        >
          Reintentar
        </button>
      </div>
    )
  } else if (draft.data === null) {
    body = <p className="chapter-scene-empty">Esta escena aún no tiene borrador</p>
  } else {
    body = <Prose markdown={draft.data.body} />
  }
  return (
    <section id={`scene-${id}`} aria-labelledby={headingId} className="chapter-scene">
      <h2 id={headingId} className="chapter-scene-title">
        <Link to={`/scenes/${id}`}>Escena {id}</Link>
      </h2>
      {body}
    </section>
  )
}

/**
 * The side index: every chapter by number and display title, the current one marked, and under
 * it the current chapter's scenes as in-page anchors. A chapter without a title of its own
 * reads "Capítulo N" rather than "N · Capítulo N".
 */
function ChapterIndex({ chapters, current }: { chapters: TocChapter[]; current: number }) {
  return (
    <nav aria-label="Índice de capítulos" className="chapter-toc">
      <p className="eyebrow">Índice</p>
      <ol className="chapter-toc-list">
        {chapters.map((chapter, index) => {
          const number = index + 1
          const ownTitle = chapterTitle(chapter.function)
          const isCurrent = index === current
          return (
            <li key={chapter.id}>
              <Link
                to={`/chapters/${chapter.id}`}
                aria-current={isCurrent ? 'page' : undefined}
                className="chapter-toc-link"
              >
                <span className="chapter-toc-number" aria-hidden="true">
                  {number}
                </span>
                {ownTitle === null ? (
                  <span>Capítulo {number}</span>
                ) : (
                  <span>
                    <span className="visually-hidden">{number} ·</span> {ownTitle}
                  </span>
                )}
              </Link>
              {isCurrent && chapter.scenes.length > 0 ? (
                <ol className="chapter-toc-scenes">
                  {chapter.scenes.map((sceneId) => (
                    <li key={sceneId}>
                      <a href={`#scene-${sceneId}`}>Escena {sceneId}</a>
                    </li>
                  ))}
                </ol>
              ) : null}
            </li>
          )
        })}
      </ol>
      <Link to="/scenes" className="chapter-toc-all">
        Ver el índice completo
      </Link>
    </nav>
  )
}

/**
 * Where the reader lands. Declarative routing keeps the previous page's scroll position, so a
 * chapter opens at its top; with `#scene-NNN` (a sheet's "Aparece en", a side-index anchor) it
 * scrolls that scene into view once the drafts above it have settled and the layout is final.
 */
function useArrivalScroll(settled: boolean) {
  const { hash: fragment } = useLocation()
  useEffect(() => {
    if (fragment === '') {
      document.documentElement.scrollTop = 0
    }
  }, [fragment])
  useEffect(() => {
    if (fragment === '' || !settled) {
      return
    }
    const target = document.getElementById(fragment.slice(1))
    // jsdom implements no scrollIntoView; every browser does.
    if (target !== null && 'scrollIntoView' in target) {
      target.scrollIntoView()
    }
  }, [fragment, settled])
}
