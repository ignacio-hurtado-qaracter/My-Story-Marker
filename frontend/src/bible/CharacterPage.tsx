// `/characters/:id`: one character's sheet from the story bible. Spec 003, FR-BIBLE-03, FR-BIBLE-05,
// AC 17. main's `.detail-head`, `.kv` card and `.prose`, with "Aparece en" linking into the reader.
import './bible.css'

import { Fragment } from 'react'
import { Link, useParams } from 'react-router'

import { Heading, Prose } from '../shared/ui'
import {
  isEntityId,
  isNotFoundError,
  mapLoadable,
  useCharacter,
  useStory,
  type Character,
  type Loadable,
} from './api'
import { AppearancePill, Appearances, type AppearanceGroups } from './AppearanceList'
import { characterAppearances } from './appearances'
import { Avatar } from './Avatar'
import { humanizeId } from './names'
import { LoadFailed, NotFoundPanel, SheetSkeleton } from './States'

export function CharacterPage() {
  const { id = '' } = useParams()
  // A malformed id is not-found without a request: the hooks that fetch live in CharacterView.
  return isEntityId(id) ? <CharacterView id={id} /> : <CharacterNotFound />
}

function CharacterNotFound() {
  return (
    <NotFoundPanel
      heading="Personaje no encontrado"
      message="No existe ningún personaje con ese identificador."
      backTo="/characters"
      backLabel="Volver a Personajes"
    />
  )
}

function CharacterView({ id }: { id: string }) {
  const character = useCharacter(id)
  const story = useStory()

  if (character.isPending) {
    return <SheetSkeleton title="Personaje · My Story Marker" />
  }
  if (character.error !== null) {
    if (isNotFoundError(character.error)) {
      return <CharacterNotFound />
    }
    return (
      <LoadFailed
        heading="No se ha podido cargar el personaje"
        error={character.error}
        onRetry={() => {
          void character.refetch()
        }}
      />
    )
  }

  const record = character.data
  const appearances: Loadable<AppearanceGroups> = mapLoadable(story, ({ chapters, scenes }) =>
    characterAppearances(record.id, chapters, scenes).map((group) => ({
      ...group,
      scenes: group.scenes.map((scene) => ({
        sceneId: scene.sceneId,
        note: scene.role === 'pov' ? 'punto de vista' : 'presente',
      })),
    })),
  )
  return (
    <article className="bible-sheet">
      <title>{`${record.name} · Personajes · My Story Marker`}</title>
      <Link to="/characters" className="bible-back">
        Todos los personajes
      </Link>
      <div className="bible-detail-head">
        <Avatar name={record.name} size="lg" />
        <div className="bible-detail-meta">
          <p className="eyebrow">Personaje</p>
          <Heading>{record.name}</Heading>
          <p className="bible-pills">
            <AppearancePill appearances={appearances} />
          </p>
        </div>
      </div>
      <div className="bible-sheet-grid">
        <CharacterFacts character={record} />
        <section className="bible-body card">
          <h2 className="bible-section-title">Retrato</h2>
          <Prose markdown={record.body} />
        </section>
        <div className="bible-side">
          <Appearances appearances={appearances} emptyText="Todavía no aparece en ninguna escena" />
        </div>
      </div>
    </article>
  )
}

function CharacterFacts({ character }: { character: Character }) {
  const competences = character.competences ?? []
  const physical = Object.entries(character.immutable_physical ?? {})
  return (
    <section className="bible-facts card">
      <h2 className="bible-section-title">Ficha</h2>
      <dl className="bible-kv">
        <dt>Quiere</dt>
        <dd>{character.wants}</dd>
        <dt>Necesita</dt>
        <dd>{character.needs}</dd>
        <dt>Mentira</dt>
        <dd>{character.lies}</dd>
        <dt>Competencias</dt>
        <dd>
          {competences.length === 0 ? (
            <span className="bible-note">Ninguna registrada</span>
          ) : (
            <ul className="bible-kv-list">
              {competences.map((competence) => (
                <li key={competence}>{competence}</li>
              ))}
            </ul>
          )}
        </dd>
        {physical.map(([attribute, value]) => (
          <Fragment key={attribute}>
            <dt>{humanizeId(attribute)}</dt>
            <dd>{value}</dd>
          </Fragment>
        ))}
      </dl>
    </section>
  )
}
