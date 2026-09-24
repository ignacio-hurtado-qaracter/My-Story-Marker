// `/`: the cover. Spec 003, FR-COVER-01..04, AC 5; plan 003 Q8, Q11.
//
// main's hero (web/index.html .hero): the orange-50 to white band, a portrait book cover in
// main's orange gradient, the eyebrow "Novela", the title as the page's h1, the premise statement
// as the lead, "Empezar a leer" and "Índice", and the decorative planet beside it. Under the
// hero, the dedication card, which the reader personalises in the page.
//
// States: the title and the dedication are local and always render. The premise loads with a
// decorative line (aria-hidden: it is an extra, not the page's content) and on any error, a 404
// included, the lead is left out; the premise's `answer` is how the book ends and is never
// rendered. The first chapter loads behind a button-shaped placeholder; on error "Empezar a
// leer" points to the index, and with no chapters it is hidden.
import './cover.css'

import { useId, useRef, useState } from 'react'
import { flushSync } from 'react-dom'
import { Link } from 'react-router'

import { PlanetHero } from '../graph3d'
import { Heading } from '../shared/ui'
import { useFirstChapterId, useProject } from './api'
import { DedicationForm } from './DedicationForm'
import { useCoverSettings, type CoverSettings } from './useCoverSettings'

/** FR-COVER-03: the title when the reader has not chosen one. */
const DEFAULT_TITLE = 'Mi novela'

export function CoverPage() {
  const { settings, save } = useCoverSettings()
  const project = useProject()
  const firstChapter = useFirstChapterId()
  const [editing, setEditing] = useState(false)
  const [storageFailed, setStorageFailed] = useState(false)
  const firstFieldRef = useRef<HTMLInputElement>(null)
  const personaliseRef = useRef<HTMLButtonElement>(null)
  const dedicationHeadingId = useId()

  const title = settings.title === '' ? DEFAULT_TITLE : settings.title
  const documentTitle = settings.title === '' ? 'Portada · My Story Marker' : `${settings.title} · My Story Marker`

  // Focus follows the form: into its first field when it opens, back to the button when it
  // closes. flushSync commits the change first, so the element to focus exists.
  function openForm() {
    flushSync(() => {
      setEditing(true)
    })
    firstFieldRef.current?.focus()
  }

  function closeForm() {
    flushSync(() => {
      setEditing(false)
    })
    personaliseRef.current?.focus()
  }

  function handleSave(next: CoverSettings) {
    setStorageFailed(!save(next))
    closeForm()
  }

  return (
    <div className="cover-page">
      <title>{documentTitle}</title>
      <section className="cover-hero">
        <div className="cover-hero-content">
          <BookCover title={title} />
          <div className="cover-hero-text">
            <p className="eyebrow">Novela</p>
            <Heading>{title}</Heading>
            <Lead statement={project.data?.premise.statement} pending={project.isPending} />
            <div className="cover-cta">
              <StartReading
                firstChapterId={firstChapter.data}
                pending={firstChapter.isPending}
                failed={firstChapter.isError}
              />
              <Link to="/scenes" className="btn-ghost cover-btn">
                Índice
              </Link>
            </div>
          </div>
        </div>
        <PlanetHero className="cover-planet" decorative />
      </section>

      <section className="cover-dedication card" aria-labelledby={dedicationHeadingId}>
        <h2 id={dedicationHeadingId} className="eyebrow cover-dedication-label">
          Dedicatoria
        </h2>
        <span className="cover-ornament" aria-hidden="true" />
        {settings.to === '' ? null : <p className="cover-dedication-to">{`Para ${settings.to}`}</p>}
        {settings.dedication === '' ? (
          <p className="cover-dedication-placeholder">Personaliza la portada para escribir aquí tu dedicatoria.</p>
        ) : (
          <p className="cover-dedication-text">{settings.dedication}</p>
        )}
        {settings.from === '' ? null : <p className="cover-dedication-from">{`— ${settings.from}`}</p>}
        {editing ? (
          <DedicationForm initial={settings} onSave={handleSave} onCancel={closeForm} firstFieldRef={firstFieldRef} />
        ) : (
          <button ref={personaliseRef} type="button" className="btn-ghost cover-btn" onClick={openForm}>
            Personalizar portada
          </button>
        )}
        {/* A live region that exists before its message does, so the message is announced. */}
        <div role="status" className="cover-storage-note">
          {storageFailed ? (
            <p>No se ha podido guardar en este navegador: la portada se mantendrá mientras no cierres la página.</p>
          ) : null}
        </div>
      </section>
    </div>
  )
}

/**
 * The portrait book cover (main's .book-card .cover, taller). Decorative: the same title is the
 * page's h1, so assistive technology reads it once.
 */
function BookCover({ title }: { title: string }) {
  return (
    <div className="cover-book" aria-hidden="true">
      <span className="cover-book-rule" />
      <span className="cover-book-title">{title}</span>
      <span className="cover-book-brand">My Story Marker</span>
    </div>
  )
}

function Lead({ statement, pending }: { statement: string | undefined; pending: boolean }) {
  if (statement !== undefined) {
    return <p className="cover-lead">{statement}</p>
  }
  return pending ? (
    <div className="cover-lead-skeleton" aria-hidden="true">
      <span />
      <span />
    </div>
  ) : null
}

interface StartReadingProps {
  firstChapterId: string | null | undefined
  pending: boolean
  failed: boolean
}

function StartReading({ firstChapterId, pending, failed }: StartReadingProps) {
  if (pending) {
    return <span className="cover-btn-skeleton" aria-hidden="true" />
  }
  if (failed) {
    return (
      <Link to="/scenes" className="cover-btn-primary">
        Empezar a leer
      </Link>
    )
  }
  if (firstChapterId === null || firstChapterId === undefined) {
    return null
  }
  return (
    <Link to={`/chapters/${firstChapterId}`} className="cover-btn-primary">
      Empezar a leer
    </Link>
  )
}
