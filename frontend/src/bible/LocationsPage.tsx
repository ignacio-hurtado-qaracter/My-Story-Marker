// `/locations`: the places of the story bible as cards, each with the chapters set in it or in one
// of its sublocations. Spec 003, FR-BIBLE-04, FR-BIBLE-05, AC 17.
import './bible.css'

import { Link } from 'react-router'

import { ErrorPanel, Heading } from '../shared/ui'
import { describeError, useLocations, useStory, type Loadable, type Location, type Story } from './api'
import { APPEARANCES_FAILED, ChapterChips } from './AppearanceList'
import { locationAppearances, type AppearanceGroup, type LocationScene } from './appearances'
import { LocationMark } from './Avatar'
import { locationName, plural } from './names'
import { CardsSkeleton } from './States'

export function LocationsPage() {
  const locations = useLocations()
  const story = useStory()
  let body
  let count = null
  if (locations.status === 'pending') {
    body = <CardsSkeleton />
  } else if (locations.status === 'error') {
    body = <ErrorPanel message={describeError(locations.error)} onRetry={locations.retry} />
  } else if (locations.data.length === 0) {
    body = <p className="bible-empty">Todavía no hay lugares</p>
  } else {
    count = <span className="pill">{plural(locations.data.length, 'lugar', 'lugares')}</span>
    body = <LocationGrid locations={locations.data} story={story} />
  }
  return (
    <section className="bible-page">
      <title>Lugares · My Story Marker</title>
      <div className="bible-hero">
        <p className="eyebrow">Biblia de la historia</p>
        <Heading>Lugares</Heading>
        <p className="bible-lead">
          Dónde ocurre la novela: cada lugar con su paleta sensorial, el lugar que lo contiene y los capítulos que se
          desarrollan en él.
        </p>
        {count}
      </div>
      {body}
    </section>
  )
}

function LocationGrid({ locations, story }: { locations: Location[]; story: Loadable<Story> }) {
  return (
    <>
      {story.status === 'error' ? <p className="bible-note bible-grid-note">{APPEARANCES_FAILED}</p> : null}
      <ul className="bible-grid">
        {locations.map((location) => (
          <LocationCard
            key={location.id}
            location={location}
            groups={
              story.status === 'success'
                ? locationAppearances(location.id, story.data.chapters, story.data.scenes, locations)
                : null
            }
          />
        ))}
      </ul>
    </>
  )
}

function LocationCard({ location, groups }: { location: Location; groups: AppearanceGroup<LocationScene>[] | null }) {
  const parent = location.parent ?? null
  return (
    <li className="bible-card card">
      <div className="bible-card-head">
        <LocationMark id={location.id} />
        <div className="bible-card-heading">
          <h2 className="bible-card-title">
            {/* The link stretches over the whole card (bible.css); the chips sit above it. */}
            <Link to={`/locations/${location.id}`} className="bible-card-link">
              {locationName(location.id)}
            </Link>
          </h2>
          <p className="bible-card-kicker">{parent === null ? 'Lugar raíz' : `Dentro de ${locationName(parent)}`}</p>
        </div>
      </div>
      <p className="bible-card-text bible-clamp">
        <span className="bible-label">Paleta sensorial</span>
        {location.sensory_palette}
      </p>
      <ChapterChips groups={groups} />
    </li>
  )
}
