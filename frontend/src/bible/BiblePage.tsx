// `/novelas/:novelId/personajes`: the character and place sheets (R03, spec 014), generated
// from the story bible. Each sheet links to the chapters of the version on screen where the
// character or place appears (fact usage per scene, else a search of the name). Spec 003's
// card look.
import './bible.css'

import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router'

import { useReaderContext } from '../reader'
import { api, errorMessage, parseApiError } from '../shared/api'
import type { Schemas } from '../shared/api'
import { ErrorPanel, Heading } from '../shared/ui'

type Entry = Schemas['BibleEntry']

async function fetchBible(novelId: string, version: number | null): Promise<Schemas['StoryBible']> {
  const { data, error, response } = await api.GET('/novels/{novel_id}/bible', {
    params: { path: { novel_id: novelId }, query: version === null ? {} : { version } },
  })
  if (!response.ok || data === undefined) {
    throw new Error(errorMessage(parseApiError(response.status, error)))
  }
  return data
}

function initials(name: string): string {
  const letters = name
    .split(/\s+/)
    .filter((word) => word.length > 0 && word[0] === word[0]?.toUpperCase())
    .slice(0, 2)
    .map((word) => word[0] ?? '')
    .join('')
  return letters === '' ? name.slice(0, 1).toUpperCase() : letters
}

export function BiblePage() {
  const { novel, version } = useReaderContext()
  const bible = useQuery({
    queryKey: ['bible', novel.id, version],
    queryFn: () => fetchBible(novel.id, version),
  })
  const title = novel.title ?? 'Mi novela'

  return (
    <section className="bible-page">
      <title>{`Personajes y lugares · ${title}`}</title>
      <div className="bible-hero">
        <p className="eyebrow">Fichas de la story bible</p>
        <Heading>Personajes y lugares</Heading>
        <p className="bible-lead">Quién aparece en la novela, dónde transcurre y en qué capítulos.</p>
      </div>
      {bible.isPending ? <p className="bible-note">Cargando las fichas…</p> : null}
      {bible.isError ? <ErrorPanel message={bible.error.message} onRetry={() => void bible.refetch()} /> : null}
      {bible.data === undefined ? null : (
        <>
          <Sheets label="Personajes" entries={bible.data.characters} />
          <Sheets label="Lugares" entries={bible.data.places} />
        </>
      )}
    </section>
  )
}

function Sheets({ label, entries }: { label: string; entries: Entry[] }) {
  if (entries.length === 0) return null
  return (
    <section aria-label={label} className="bible-sheet-group">
      <h2 className="bible-section-title">{label}</h2>
      <ul className="bible-grid">
        {entries.map((entry) => (
          <Sheet key={entry.id} entry={entry} />
        ))}
      </ul>
    </section>
  )
}

function Sheet({ entry }: { entry: Entry }) {
  const { href } = useReaderContext()
  const kind = entry.kind === 'character' ? 'bible-avatar' : 'bible-mark'
  return (
    <li className="bible-card card" data-testid="bible-sheet">
      <div className="bible-card-head">
        <span aria-hidden="true" className={kind}>
          {entry.kind === 'character' ? initials(entry.name) : <span className="bible-mark-letters">{initials(entry.name)}</span>}
        </span>
        <div className="bible-card-heading">
          <h3 className="bible-card-title">{entry.name}</h3>
          {entry.role === '' ? null : <p className="bible-card-kicker">{entry.role}</p>}
        </div>
      </div>
      {entry.description === '' ? null : <p className="bible-card-text">{entry.description}</p>}
      <div className="bible-chips">
        <span className="bible-label">Aparece en</span>
        {(entry.chapters ?? []).length === 0 ? (
          <p className="bible-card-text">Ningún capítulo de esta versión.</p>
        ) : (
          <ul className="bible-chip-list">
            {(entry.chapters ?? []).map((n) => (
              <li key={n}>
                <Link className="bible-chip" to={href(`capitulos/${String(n)}`)}>
                  {`Capítulo ${String(n)}`}
                </Link>
              </li>
            ))}
          </ul>
        )}
      </div>
    </li>
  )
}
