// `/`: the novels in the story bible, each leading to its reader (spec 014).
import './reader.css'

import { Link } from 'react-router'

import { ErrorPanel, Heading } from '../shared/ui'
import { useNovels } from './api'
import { readerHref } from './context'

export function NovelsPage() {
  const novels = useNovels()
  return (
    <section className="reader-page">
      <title>Novelas · My Story Marker</title>
      <div className="reader-hero">
        <p className="eyebrow">Biblioteca</p>
        <Heading>Novelas</Heading>
        <p className="reader-lead">Novelas regalo generadas por el harness. Elige una para leerla.</p>
      </div>
      {novels.isPending ? <p className="reader-state">Cargando las novelas…</p> : null}
      {novels.isError ? <ErrorPanel message={novels.error.message} onRetry={() => void novels.refetch()} /> : null}
      {novels.data?.length === 0 ? (
        <p className="reader-state">
          Aún no hay novelas. Genera una con <code>uv run python -m app.novel.cli generate</code>.
        </p>
      ) : null}
      <ul className="reader-novels">
        {(novels.data ?? []).map((novel) => (
          <li key={novel.id} className="card reader-novel">
            <p className="eyebrow">{novel.current_version == null ? 'En preparación' : `Versión ${String(novel.current_version)}`}</p>
            <h2 className="reader-novel-title">
              <Link to={readerHref(novel.id, null)}>{novel.title ?? 'Novela sin título'}</Link>
            </h2>
            {novel.recipient == null ? null : <p className="reader-toc-meta">{`Para ${novel.recipient}`}</p>}
          </li>
        ))}
      </ul>
    </section>
  )
}
