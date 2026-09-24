// What the reader's layout hands to the pages below it (cover, index, chapter, sheets):
// the novel, the version being read, and how to build links that keep that version.
// Spec 014. Pages read it with `useReaderContext()`; they never fetch the novel again.
import { useOutletContext } from 'react-router'

import type { NovelDetail, VersionInfo } from './api'

export interface ReaderContext {
  novel: NovelDetail
  /** The version on screen: `?v=` when given, else the latest published; null when none. */
  version: number | null
  versionInfo: VersionInfo | null
  /** `/novelas/<id>/<sub>?v=<version>`. */
  href: (sub?: string) => string
}

export function readerHref(novelId: string, version: number | null, sub = ''): string {
  const base = `/novelas/${encodeURIComponent(novelId)}${sub === '' ? '' : `/${sub}`}`
  return version === null ? base : `${base}?v=${String(version)}`
}

/** The `?v=` search parameter, when it is a positive integer. */
export function parseVersion(raw: string | null): number | null {
  if (raw === null || !/^\d+$/.test(raw)) return null
  const value = Number(raw)
  return value > 0 ? value : null
}

export function useReaderContext(): ReaderContext {
  return useOutletContext<ReaderContext>()
}
