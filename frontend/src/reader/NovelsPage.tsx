// `/`: the library — one card per novel in the story bible, each leading to its reader
// (spec 014), with its status, version, chapter count and filter chips (spec 019).
import './reader.css'
import './library.css'

import { useState } from 'react'
import { Link } from 'react-router'

import { ErrorPanel, Heading } from '../shared/ui'
import { pdfHref, useChapterIndex, useNovel, useNovels } from './api'
import type { NovelDetail, NovelSummary, VersionInfo } from './api'
import { readerHref } from './context'

type Filter = 'all' | 'published' | 'other'

const FILTERS: readonly { id: Filter; label: string }[] = [
  { id: 'all', label: 'Todas' },
  { id: 'published', label: 'Publicadas' },
  { id: 'other', label: 'Otras' },
]

type Badge = { label: string; tone: 'ok' | 'fail' | 'warn' | 'neutral' }

/** The card's status badge (spec 019, Design): from the novel and its latest version. */
function statusBadge(novel: NovelSummary, detail: NovelDetail | undefined): Badge {
  if (novel.status === 'published') return { label: 'Publicada', tone: 'ok' }
  const latest = (detail?.versions ?? []).reduce<VersionInfo | null>(
    (best, v) => (best === null || v.version > best.version ? v : best),
    null,
  )
  if (latest?.status === 'blocked') return { label: 'Bloqueada', tone: 'fail' }
  if (novel.status === 'stopped_error') return { label: 'Parada', tone: 'warn' }
  return { label: 'En curso', tone: 'neutral' }
}

function matches(filter: Filter, novel: NovelSummary): boolean {
  if (filter === 'all') return true
  return (novel.status === 'published') === (filter === 'published')
}

function ChapterCount({ novelId, version }: { novelId: string; version: number }) {
  const index = useChapterIndex(novelId, version)
  if (index.data === undefined) return <>…</>
  const n = index.data.chapters.length
  return <>{n === 1 ? '1 capítulo' : `${String(n)} capítulos`}</>
}

function NovelCard({ novel }: { novel: NovelSummary }) {
  const detail = useNovel(novel.id)
  const badge = statusBadge(novel, detail.data)
  const version = novel.current_version ?? null
  const title = novel.title ?? 'Novela sin título'
  const versions = detail.data?.versions?.length

  return (
    <li className="card library-card">
      <div className="library-card-top">
        <span className={`library-badge library-badge-${badge.tone}`}>{badge.label}</span>
        {version === null ? null : <span className="pill pill-neutral">{`Versión ${String(version)}`}</span>}
      </div>
      <h2 className="library-card-title">
        <Link to={readerHref(novel.id, null)}>{title}</Link>
      </h2>
      <p className="library-card-recipient">{novel.recipient == null ? 'Sin destinatario' : `Para ${novel.recipient}`}</p>
      <p className="library-card-meta">
        {version === null ? 'Aún sin versión publicada' : <ChapterCount novelId={novel.id} version={version} />}
        {versions === undefined || versions < 2 ? null : ` · ${String(versions)} versiones`}
      </p>
      <nav className="library-card-links" aria-label={`Abrir ${title}`}>
        <Link className="btn-ghost" to={readerHref(novel.id, null)}>
          Portada
        </Link>
        {version === null ? null : (
          <>
            <Link className="btn-ghost" to={readerHref(novel.id, version, 'indice')}>
              Índice
            </Link>
            <a className="btn-ghost" href={pdfHref(novel.id, version)}>
              PDF
            </a>
          </>
        )}
      </nav>
    </li>
  )
}

export function NovelsPage() {
  const novels = useNovels()
  const [filter, setFilter] = useState<Filter>('all')
  const all = novels.data ?? []
  const shown = all.filter((novel) => matches(filter, novel))

  return (
    <section className="reader-page">
      <title>Biblioteca · My Story Marker</title>
      <div className="reader-hero">
        <p className="eyebrow">Novelas regalo</p>
        <Heading>Biblioteca</Heading>
        <p className="reader-lead">Las novelas generadas por el harness. Elige una para leerla o descargarla en PDF.</p>
      </div>
      {novels.isPending ? <p className="reader-state">Cargando las novelas…</p> : null}
      {novels.isError ? <ErrorPanel message={novels.error.message} onRetry={() => void novels.refetch()} /> : null}
      {novels.data?.length === 0 ? (
        <p className="reader-state">
          Aún no hay novelas. Genera una con <code>uv run python -m app.novel.cli generate</code>.
        </p>
      ) : null}
      {all.length === 0 ? null : (
        <div className="library-filters" role="group" aria-label="Filtrar novelas">
          {FILTERS.map((item) => {
            const count = all.filter((novel) => matches(item.id, novel)).length
            return (
              <button
                key={item.id}
                type="button"
                className="library-chip"
                aria-pressed={filter === item.id}
                onClick={() => {
                  setFilter(item.id)
                }}
              >
                {item.label}
                <span className="library-chip-count">{count}</span>
              </button>
            )
          })}
        </div>
      )}
      {all.length > 0 && shown.length === 0 ? <p className="reader-state">Ninguna novela en este filtro.</p> : null}
      <ul className="library-grid" aria-label="Novelas">
        {shown.map((novel) => (
          <NovelCard key={novel.id} novel={novel} />
        ))}
      </ul>
    </section>
  )
}
