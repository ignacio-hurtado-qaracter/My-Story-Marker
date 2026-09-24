// `/novelas/:novelId/capitulos/:n`: one chapter (spec 014). Selecting text in it shows a
// floating "Pedir un cambio" button; the form it opens sends the fragment and the request to
// the backend (R05), which regenerates only the chapters that use the fact.
//
// The browser's selection is an external system, so it is read through a `selectionchange`
// subscription in an effect (the one legitimate kind); everything else happens in handlers.
import { useEffect, useRef, useState } from 'react'
import { Link, useParams } from 'react-router'

import { ErrorPanel, Prose } from '../shared/ui'
import { useChapter } from './api'
import { ChangeRequestPanel } from './ChangeRequestPanel'
import { useReaderContext } from './context'
import { NoVersion } from './NoVersion'

interface Selected {
  text: string
  top: number
  left: number
}

const MIN_SELECTION = 2

export function ChapterPage() {
  const { novel, version } = useReaderContext()
  const { n = '' } = useParams()
  const number = Number(n)
  if (version === null) return <NoVersion />
  if (!Number.isInteger(number) || number < 1) {
    return <ErrorPanel message="Ese capítulo no existe." />
  }
  // Keyed, so moving to another chapter starts with no selection and the form closed.
  return <Chapter key={`${String(version)}-${String(number)}`} novelId={novel.id} version={version} n={number} />
}

function Chapter({ novelId, version, n }: { novelId: string; version: number; n: number }) {
  const { novel, href } = useReaderContext()
  const chapter = useChapter(novelId, version, n)
  const articleRef = useRef<HTMLDivElement>(null)
  const [selected, setSelected] = useState<Selected | null>(null)
  const [fragment, setFragment] = useState<string | null>(null)

  useEffect(() => {
    function onSelectionChange() {
      const article = articleRef.current
      const selection = document.getSelection()
      const text = selection?.toString().trim() ?? ''
      if (article === null || selection === null || selection.rangeCount === 0 || text.length < MIN_SELECTION) {
        setSelected(null)
        return
      }
      const range = selection.getRangeAt(0)
      if (!article.contains(range.commonAncestorContainer)) {
        setSelected(null)
        return
      }
      const box = range.getBoundingClientRect()
      const frame = article.getBoundingClientRect()
      setSelected({ text, top: box.bottom - frame.top + 8, left: Math.max(0, box.left - frame.left) })
    }
    document.addEventListener('selectionchange', onSelectionChange)
    return () => {
      document.removeEventListener('selectionchange', onSelectionChange)
    }
  }, [])

  if (chapter.isPending) return <p className="reader-state">Cargando el capítulo…</p>
  if (chapter.isError) return <ErrorPanel message={chapter.error.message} onRetry={() => void chapter.refetch()} />

  const data = chapter.data
  const title = novel.title ?? 'Mi novela'

  function openForm(text: string) {
    setFragment(text)
    setSelected(null)
  }

  return (
    <article className="reader-page reader-chapter">
      <title>{`${data.title} · ${title}`}</title>
      <header className="reader-chapter-head">
        <p className="eyebrow">{`Capítulo ${String(data.n)} · versión ${String(version)}`}</p>
        <h1 className="heading heading-1">{data.title}</h1>
        {data.changed ? (
          <p>
            <span className="pill reader-changed">modificado</span>{' '}
            <span className="reader-toc-meta">Este capítulo cambió respecto a la versión anterior.</span>
          </p>
        ) : null}
      </header>
      <div ref={articleRef} className="reader-text" data-testid="chapter-text">
        <Prose markdown={data.text} />
        {selected === null ? null : (
          <button
            type="button"
            className="reader-float"
            style={{ top: selected.top, left: selected.left }}
            // Keep the selection alive: a mousedown on the button would otherwise clear it.
            onMouseDown={(event) => {
              event.preventDefault()
            }}
            onClick={() => {
              openForm(selected.text)
            }}
          >
            Pedir un cambio
          </button>
        )}
      </div>
      {fragment === null ? (
        <p className="reader-change-hint">
          Selecciona un fragmento para pedir un cambio, o{' '}
          <button type="button" className="btn-ghost" onClick={() => {
            openForm('')
          }}>
            pide un cambio sin fragmento
          </button>
        </p>
      ) : (
        <ChangeRequestPanel
          novelId={novelId}
          fragment={fragment}
          onClose={() => {
            setFragment(null)
          }}
        />
      )}
      <nav aria-label="Capítulos" className="reader-pager">
        {data.previous == null ? <span /> : (
          <Link to={href(`capitulos/${String(data.previous)}`)}>← Capítulo anterior</Link>
        )}
        <Link to={href('indice')}>Índice</Link>
        {data.next == null ? <span /> : <Link to={href(`capitulos/${String(data.next)}`)}>Capítulo siguiente →</Link>}
      </nav>
    </article>
  )
}
