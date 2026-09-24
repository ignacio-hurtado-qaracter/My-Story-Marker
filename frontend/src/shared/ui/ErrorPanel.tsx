// The error state of a screen. Used by app/ (error boundary), scenes/ and graph3d/: spec 002,
// FR-UI-01. The message comes from shared/api's errorMessage (FR-API-04) or a screen's own text.
// Look: spec 003, FR-UI3-02.
import './ErrorPanel.css'

export interface ErrorPanelProps {
  message: string
  /** Shown only when retrying can succeed; omitted for errors a retry cannot fix. */
  onRetry?: () => void
}

export function ErrorPanel({ message, onRetry }: ErrorPanelProps) {
  return (
    <div role="alert" className="error-panel">
      <p>{message}</p>
      {onRetry === undefined ? null : (
        <button type="button" className="btn-ghost" onClick={onRetry}>
          Reintentar
        </button>
      )}
    </div>
  )
}
