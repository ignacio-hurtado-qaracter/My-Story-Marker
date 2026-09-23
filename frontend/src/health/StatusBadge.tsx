// A small live status line. Used only by the health badge, so it lives here: spec 002, FR-UI-01, P16.
import type { ReactNode } from 'react'

export type StatusTone = 'pending' | 'ok' | 'error'

export interface StatusBadgeProps {
  /** The accessible name of the region, e.g. what the status is about. */
  label: string
  tone: StatusTone
  children: ReactNode
}

export function StatusBadge({ label, tone, children }: StatusBadgeProps) {
  return (
    <span role="status" aria-live="polite" aria-label={label} className={`status-badge status-badge-${tone}`}>
      {children}
    </span>
  )
}
