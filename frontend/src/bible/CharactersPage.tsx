// `/characters`: the cast of the story bible as cards, each with the chapters the character appears
// in. Spec 003, FR-BIBLE-02, FR-BIBLE-05, AC 17. main's `.characters` grid and `.character` card.
import './bible.css'

import { Link } from 'react-router'

import { ErrorPanel, Heading } from '../shared/ui'
import { describeError, useCharacters, useStory, type Character, type Loadable, type Story } from './api'
import { APPEARANCES_FAILED, ChapterChips } from './AppearanceList'
import { characterAppearances, type AppearanceGroup, type CharacterScene } from './appearances'
import { Avatar } from './Avatar'
import { plural } from './names'
import { CardsSkeleton } from './States'

export function CharactersPage() {
  const characters = useCharacters()
  const story = useStory()
  let body
  let count = null
  if (characters.status === 'pending') {
    body = <CardsSkeleton />
  } else if (characters.status === 'error') {
    body = <ErrorPanel message={describeError(characters.error)} onRetry={characters.retry} />
  } else if (characters.data.length === 0) {
    body = <p className="bible-empty">Todavía no hay personajes</p>
  } else {
    count = <span className="pill">{plural(characters.data.length, 'personaje', 'personajes')}</span>
    body = <CharacterGrid characters={characters.data} story={story} />
  }
  return (
    <section className="bible-page">
      <title>Personajes · My Story Marker</title>
      <div className="bible-hero">
        <p className="eyebrow">Biblia de la historia</p>
        <Heading>Personajes</Heading>
        <p className="bible-lead">
          Quién vive en la novela: lo que cada personaje quiere, lo que necesita y los capítulos en los que aparece.
        </p>
        {count}
      </div>
      {body}
    </section>
  )
}

function CharacterGrid({ characters, story }: { characters: Character[]; story: Loadable<Story> }) {
  return (
    <>
      {story.status === 'error' ? <p className="bible-note bible-grid-note">{APPEARANCES_FAILED}</p> : null}
      <ul className="bible-grid">
        {characters.map((character) => (
          <CharacterCard
            key={character.id}
            character={character}
            groups={
              story.status === 'success'
                ? characterAppearances(character.id, story.data.chapters, story.data.scenes)
                : null
            }
          />
        ))}
      </ul>
    </>
  )
}

/** main's `.character .role` line: what part the character plays in the scenes written so far. */
function roleLine(groups: AppearanceGroup<CharacterScene>[] | null): string {
  if (groups === null) {
    return 'Personaje'
  }
  const scenes = groups.flatMap((group) => group.scenes)
  const pov = scenes.filter((scene) => scene.role === 'pov').length
  if (pov > 0) {
    return `Punto de vista en ${plural(pov, 'escena', 'escenas')}`
  }
  return scenes.length > 0 ? `Presente en ${plural(scenes.length, 'escena', 'escenas')}` : 'Todavía sin escenas'
}

function CharacterCard({
  character,
  groups,
}: {
  character: Character
  groups: AppearanceGroup<CharacterScene>[] | null
}) {
  return (
    <li className="bible-card card">
      <div className="bible-card-head">
        <Avatar name={character.name} />
        <div className="bible-card-heading">
          <h2 className="bible-card-title">
            {/* The link stretches over the whole card (bible.css); the chips sit above it. */}
            <Link to={`/characters/${character.id}`} className="bible-card-link">
              {character.name}
            </Link>
          </h2>
          <p className="bible-card-kicker">{roleLine(groups)}</p>
        </div>
      </div>
      <p className="bible-card-text">
        <span className="bible-label">Quiere</span>
        {character.wants}
      </p>
      <ChapterChips groups={groups} />
    </li>
  )
}
