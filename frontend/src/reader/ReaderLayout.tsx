// `/novelas/:novelId/*`: the reader's frame (spec 014). It loads the novel once, resolves the
// version on screen (`?v=`, else the latest published — architecture, "The reader"), and
// renders the reader's own navigation: Portada · Índice · Personajes y lugares, the version
// selector (earlier versions stay readable, R07) and the PDF download.
import './reader.css'

import { useId, type ChangeEvent } from 'react'
import { NavLink, Outlet, useNavigate, useParams, useSearchParams } from 'react-router'

import { ErrorPanel } from '../shared/ui'
import { pdfHref, useNovel } from './api'
import { parseVersion, readerHref, type ReaderContext } from './context'

export function ReaderLayout() {
  const { novelId = '' } = useParams()
  const [search] = useSearchParams()
  const novel = useNovel(novelId)
  const navigate = useNavigate()
  const selectId = useId()

  if (novel.isPending) {
    return <p className="reader-state">Cargando la novela…</p>
  }
  if (novel.isError) {
    return <ErrorPanel message={novel.error.message} onRetry={() => void novel.refetch()} />
  }

  const detail = novel.data
  const version = parseVersion(search.get('v')) ?? detail.current_version ?? null
  const versionInfo = (detail.versions ?? []).find((v) => v.version === version) ?? null
  const published = (detail.versions ?? []).filter((v) => v.status === 'published' || v.version === version)
  const context: ReaderContext = {
    novel: detail,
    version,
    versionInfo,
    href: (sub = '') => readerHref(detail.id, version, sub),
  }

  function changeVersion(event: ChangeEvent<HTMLSelectElement>) {
    void navigate(readerHref(detail.id, Number(event.target.value), 'indice'))
  }

  return (
    <div className="reader">
      <nav aria-label="Lectura" className="reader-nav">
        <ul>
          <li>
            <NavLink end to={context.href()}>
              Portada
            </NavLink>
          </li>
          <li>
            <NavLink to={context.href('indice')}>Índice</NavLink>
          </li>
          <li>
            <NavLink to={context.href('personajes')}>Personajes y lugares</NavLink>
          </li>
        </ul>
        <div className="reader-nav-tools">
          {published.length > 0 && version !== null ? (
            <>
              <label htmlFor={selectId} className="reader-nav-label">
                Versión
              </label>
              <select id={selectId} value={version} onChange={changeVersion} className="reader-select">
                {published.map((v) => (
                  <option key={v.version} value={v.version}>
                    {`v${String(v.version)}${v.version === detail.current_version ? ' (actual)' : ''}`}
                  </option>
                ))}
              </select>
              <a className="btn-ghost reader-pdf" href={pdfHref(detail.id, version)} download>
                PDF
              </a>
            </>
          ) : null}
        </div>
      </nav>
      <Outlet context={context} />
    </div>
  )
}
