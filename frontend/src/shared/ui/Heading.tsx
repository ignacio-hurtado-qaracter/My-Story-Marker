// A page or section heading. Used by app/ (not-found), scenes/ and graph3d/: spec 002, FR-UI-01.
import type { ReactNode } from 'react'

export interface HeadingProps {
  /** 1 for the page title; 2 and 3 for sections inside it. */
  level?: 1 | 2 | 3
  children: ReactNode
}

export function Heading({ level = 1, children }: HeadingProps) {
  const Tag = `h${String(level)}` as 'h1' | 'h2' | 'h3'
  return <Tag className={`heading heading-${String(level)}`}>{children}</Tag>
}
