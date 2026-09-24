// `/novelas/:novelId/indice`: the navigable chapter index (R01, R02), with the chapters changed
// against the parent version marked "modificado" and a "Novedades" note (R06). Spec 014.
import { Link } from 'react-router'

import { ErrorPanel, Heading } from '../shared/ui'
import { useChapterIndex } from './api'
import { useReaderContext } from './context'
import { NoVersion } from './NoVersion'

export function ChapterIndexPage() {
  const { novel, version } = useReaderContext()
  if (version === null) return <NoVersion />
  return <ChapterIndex novelId={novel.id} version={version} />
}

function ChapterIndex({ novelId, version }: { novelId: string; version: number }) {
  const { novel, versionInfo, href } = useReaderContext()
  const index = useChapterIndex(novelId, version)
  const title = novel.title ?? 'Mi novela'
  const changed = versionInfo?.changed_chapters ?? []
  const parent = versionInfo?.parent ?? null

  return (
    <section className="reader-page">
      <title>{`Índice · ${title}`}</title>
      <div className="reader-hero">
        <p className="eyebrow">{`${title} · versión ${String(version)}`}</p>
        <Heading>Índice</Heading>
        {parent !== null && changed.length > 0 ? (
          <p className="reader-news" role="note">
            <strong>Novedades:</strong>{' '}
            {`esta versión cambia ${changed.length === 1 ? 'el capítulo' : 'los capítulos'} ${changed.join(', ')} respecto a la versión ${String(parent)}, que se conserva.`}
          </p>
        ) : null}
      </div>
      {index.isPending ? <p className="reader-state">Cargando el índice…</p> : null}
      {index.isError ? <ErrorPanel message={index.error.message} onRetry={() => void index.refetch()} /> : null}
      {index.data === undefined ? null : index.data.chapters.length === 0 ? (
        <p className="reader-state">Esta versión aún no tiene capítulos.</p>
      ) : (
        <ol className="reader-toc" aria-label="Capítulos">
          {index.data.chapters.map((chapter) => (
            <li key={chapter.n} className="reader-toc-item card">
              <span className="reader-toc-number" aria-hidden="true">
                {chapter.n}
              </span>
              <div className="reader-toc-body">
                <Link to={href(`capitulos/${String(chapter.n)}`)} className="reader-toc-link">
                  {`Capítulo ${String(chapter.n)}: ${chapter.title}`}
                </Link>
                <span className="reader-toc-meta">{`${String(chapter.words)} palabras`}</span>
              </div>
              {chapter.changed_vs_parent ? <span className="pill reader-changed">modificado</span> : null}
            </li>
          ))}
        </ol>
      )}
    </section>
  )
}
