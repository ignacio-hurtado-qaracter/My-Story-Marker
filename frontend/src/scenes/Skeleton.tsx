// The loading state of a scenes/ screen. Used only by scenes/, so it lives here (FR-UI-01, P16).
// Spec 003, FR-SCN3-03: a light surface block that keeps its status and its text.
import './scenes.css'

export interface SkeletonProps {
  /** How many placeholder lines to draw under the text. */
  lines?: number
}

export function Skeleton({ lines = 3 }: SkeletonProps) {
  return (
    <div role="status" aria-busy="true" className="skeleton">
      <p>Cargando…</p>
      <ul aria-hidden="true" className="skeleton-lines">
        {Array.from({ length: lines }, (_, index) => (
          <li key={index} className="skeleton-line" />
        ))}
      </ul>
    </div>
  )
}
