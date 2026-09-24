// `/novelas/:novelId`: the cover. Spec 003's look (main's hero, the portrait book cover, the
// decorative planet, the dedication card); spec 014 replaces its data: the title, the
// recipient and the personalised dedication come from the story bible through the API (R04),
// no longer from this browser's localStorage.
import './cover.css'

import { useId } from 'react'
import { Link } from 'react-router'

import { PlanetHero } from '../graph3d'
import { useReaderContext } from '../reader'
import { Heading } from '../shared/ui'

/** When the planner has not named the book yet. */
const DEFAULT_TITLE = 'Mi novela'

export function CoverPage() {
  const { novel, version, href } = useReaderContext()
  const dedicationHeadingId = useId()
  const title = novel.title ?? DEFAULT_TITLE
  const dedication = (novel.dedication ?? '').trim()

  return (
    <div className="cover-page">
      <title>{`${title} · My Story Marker`}</title>
      <section className="cover-hero">
        <div className="cover-hero-content">
          <BookCover title={title} />
          <div className="cover-hero-text">
            <p className="eyebrow">Novela</p>
            <Heading>{title}</Heading>
            {novel.recipient == null ? null : <p className="cover-lead">{`Una novela para ${novel.recipient}`}</p>}
            {version === null ? null : (
              <div className="cover-cta">
                <Link to={href('capitulos/1')} className="cover-btn-primary">
                  Empezar a leer
                </Link>
                <Link to={href('indice')} className="btn-ghost cover-btn">
                  Índice
                </Link>
              </div>
            )}
          </div>
        </div>
        <PlanetHero className="cover-planet" decorative />
      </section>

      <section className="cover-dedication card" aria-labelledby={dedicationHeadingId}>
        <h2 id={dedicationHeadingId} className="eyebrow cover-dedication-label">
          Dedicatoria
        </h2>
        <span className="cover-ornament" aria-hidden="true" />
        {novel.recipient == null ? null : <p className="cover-dedication-to">{`Para ${novel.recipient}`}</p>}
        {dedication === '' ? (
          <p className="cover-dedication-placeholder">Esta novela aún no tiene dedicatoria.</p>
        ) : (
          dedication.split(/\n\s*\n/).map((paragraph, i) => (
            // The dedication's paragraphs have no identity beyond their order and text.
            <p key={`${String(i)}-${paragraph.slice(0, 12)}`} className="cover-dedication-text">

              {paragraph}
            </p>
          ))
        )}
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
