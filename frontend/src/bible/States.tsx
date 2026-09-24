// The loading, not-found and failed states of the bible/ screens. Spec 003, FR-BIBLE-05 and
// FR-IA-03. Used only by bible/, so they live here (spec 002, FR-UI-01 placement rule).
import './bible.css'

import { Link } from 'react-router'

import { ErrorPanel, Heading } from '../shared/ui'
import { describeError } from './api'

/** A list screen loading: placeholder cards under a status that keeps its text. */
export function CardsSkeleton({ cards = 3 }: { cards?: number }) {
  return (
    <div role="status" aria-busy="true" className="bible-skeleton">
      <p className="bible-skeleton-label">Cargando…</p>
      <ul aria-hidden="true" className="bible-grid">
        {Array.from({ length: cards }, (_, index) => (
          <li key={index} className="bible-skeleton-card">
            <span className="bible-skeleton-circle bible-shimmer" />
            <span className="bible-skeleton-line bible-shimmer" />
            <span className="bible-skeleton-line bible-skeleton-short bible-shimmer" />
          </li>
        ))}
      </ul>
    </div>
  )
}

/** A sheet loading: the detail head and a few lines. */
export function SheetSkeleton({ title }: { title: string }) {
  return (
    <div role="status" aria-busy="true" className="bible-skeleton">
      <title>{title}</title>
      <p className="bible-skeleton-label">Cargando…</p>
      <div aria-hidden="true" className="bible-skeleton-sheet">
        <span className="bible-skeleton-circle bible-skeleton-circle-lg bible-shimmer" />
        <span className="bible-skeleton-lines">
          <span className="bible-skeleton-line bible-shimmer" />
          <span className="bible-skeleton-line bible-skeleton-short bible-shimmer" />
          <span className="bible-skeleton-line bible-shimmer" />
        </span>
      </div>
    </div>
  )
}

export interface NotFoundPanelProps {
  /** "Personaje no encontrado", "Lugar no encontrado". */
  heading: string
  message: string
  backTo: string
  backLabel: string
}

/** An unknown id: a centred panel with a way back and no retry (retrying cannot help). */
export function NotFoundPanel({ heading, message, backTo, backLabel }: NotFoundPanelProps) {
  return (
    <section className="bible-panel">
      <title>{`${heading} · My Story Marker`}</title>
      <p className="eyebrow">Biblia de la historia</p>
      <Heading>{heading}</Heading>
      <p>{message}</p>
      <Link to={backTo} className="btn-ghost">
        {backLabel}
      </Link>
    </section>
  )
}

export interface LoadFailedProps {
  heading: string
  error: unknown
  onRetry: () => void
}

/** A record that failed for any other reason: the page keeps its h1 and offers a retry. */
export function LoadFailed({ heading, error, onRetry }: LoadFailedProps) {
  return (
    <section className="bible-failed">
      <title>{`${heading} · My Story Marker`}</title>
      <Heading>{heading}</Heading>
      <ErrorPanel message={describeError(error)} onRetry={onRetry} />
    </section>
  )
}
