// `/locations/:id`: one location's sheet from the story bible. Spec 003, FR-BIBLE-04, FR-BIBLE-05,
// AC 17. The name is derived from the id (spec R2-5); appearances count the scenes set here and,
// "vía" a sublocation, those set anywhere below it in the `parent` tree.
import './bible.css'

import { Link, useParams } from 'react-router'

import { Heading, Prose } from '../shared/ui'
import {
  bothLoadable,
  isEntityId,
  isNotFoundError,
  mapLoadable,
  useLocation,
  useLocations,
  useStory,
  type Loadable,
  type Location,
} from './api'
import { AppearancePill, Appearances, type AppearanceGroups } from './AppearanceList'
import { locationAppearances, sublocations } from './appearances'
import { LocationMark } from './Avatar'
import { locationName } from './names'
import { LoadFailed, NotFoundPanel, SheetSkeleton } from './States'

export function LocationPage() {
  const { id = '' } = useParams()
  // A malformed id is not-found without a request: the hooks that fetch live in LocationView.
  return isEntityId(id) ? <LocationView id={id} /> : <LocationNotFound />
}

function LocationNotFound() {
  return (
    <NotFoundPanel
      heading="Lugar no encontrado"
      message="No existe ningún lugar con ese identificador."
      backTo="/locations"
      backLabel="Volver a Lugares"
    />
  )
}

function LocationLink({ id }: { id: string }) {
  return <Link to={`/locations/${id}`}>{locationName(id)}</Link>
}

function LocationView({ id }: { id: string }) {
  const location = useLocation(id)
  const locations = useLocations()
  const story = useStory()

  if (location.isPending) {
    return <SheetSkeleton title="Lugar · My Story Marker" />
  }
  if (location.error !== null) {
    if (isNotFoundError(location.error)) {
      return <LocationNotFound />
    }
    return (
      <LoadFailed
        heading="No se ha podido cargar el lugar"
        error={location.error}
        onRetry={() => {
          void location.refetch()
        }}
      />
    )
  }

  const record = location.data
  const name = locationName(record.id)
  const parent = record.parent ?? null
  // The parent tree needs every location record; the sheet renders without it.
  const appearances: Loadable<AppearanceGroups> = mapLoadable(
    bothLoadable(story, locations),
    ([{ chapters, scenes }, tree]) =>
      locationAppearances(record.id, chapters, scenes, tree).map((group) => ({
        ...group,
        scenes: group.scenes.map((scene) => ({
          sceneId: scene.sceneId,
          note: scene.via === null ? 'aquí' : `vía ${locationName(scene.via)}`,
        })),
      })),
  )
  return (
    <article className="bible-sheet">
      <title>{`${name} · Lugares · My Story Marker`}</title>
      <Link to="/locations" className="bible-back">
        Todos los lugares
      </Link>
      <div className="bible-detail-head">
        <LocationMark id={record.id} size="lg" />
        <div className="bible-detail-meta">
          <p className="eyebrow">Lugar</p>
          <Heading>{name}</Heading>
          <p className="bible-parent">
            {parent === null ? (
              'Lugar raíz'
            ) : (
              <>
                Dentro de <LocationLink id={parent} />
              </>
            )}
          </p>
          <p className="bible-pills">
            <AppearancePill appearances={appearances} />
          </p>
        </div>
      </div>
      <div className="bible-sheet-grid">
        <LocationFacts location={record} tree={locations} />
        <section className="bible-body card">
          <h2 className="bible-section-title">Descripción</h2>
          <Prose markdown={record.body} />
        </section>
        <div className="bible-side">
          <Appearances appearances={appearances} emptyText="Todavía no hay escenas en este lugar" />
        </div>
      </div>
    </article>
  )
}

function LocationFacts({ location, tree }: { location: Location; tree: Loadable<Location[]> }) {
  const access = location.access ?? []
  return (
    <section className="bible-facts card">
      <h2 className="bible-section-title">Ficha</h2>
      <dl className="bible-kv">
        <dt>Paleta sensorial</dt>
        <dd>{location.sensory_palette}</dd>
        <dt>Geometría</dt>
        <dd>{location.geometry}</dd>
        <dt>Accesos</dt>
        <dd>
          {access.length === 0 ? (
            <span className="bible-note">Ninguno registrado</span>
          ) : (
            <ul className="bible-kv-list">
              {access.map((entry, index) => (
                <li key={`${entry.from}-${String(index)}`}>
                  desde <LocationLink id={entry.from} />
                  {` · ${String(entry.hours)} h`}
                </li>
              ))}
            </ul>
          )}
        </dd>
        <dt>Sublugares</dt>
        <dd>
          <Sublocations id={location.id} locations={tree} />
        </dd>
      </dl>
    </section>
  )
}

function Sublocations({ id, locations }: { id: string; locations: Loadable<Location[]> }) {
  if (locations.status === 'pending') {
    return <span className="bible-note">Cargando…</span>
  }
  if (locations.status === 'error') {
    return <span className="bible-note">No se han podido cargar los sublugares</span>
  }
  const ids = sublocations(id, locations.data)
  if (ids.length === 0) {
    return <span className="bible-note">Ninguno</span>
  }
  return (
    <ul className="bible-kv-list">
      {ids.map((child) => (
        <li key={child}>
          <LocationLink id={child} />
        </li>
      ))}
    </ul>
  )
}
