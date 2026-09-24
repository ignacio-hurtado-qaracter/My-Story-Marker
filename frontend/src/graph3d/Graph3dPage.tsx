// The /graph3d page: a heading and the decorative planet with its pause toggle, in main's hero
// look. Spec 002, FR-3D-01; spec 003, FR-3D-03..05. The toggle and the canvas live in
// PlanetHero, which the cover mounts too (plan 003 Q8).
// Loading, error and loaded states come from PlanetHero's LazyCanvas; empty does not apply,
// since the page shows no data.
import { Heading } from '../shared/ui'
import './graph3d.css'
import type { LazyCanvasProps } from './LazyCanvas'
import { PlanetHero } from './PlanetHero'

/** The props exist for the tests (AC 18; spec 003, AC 7); app/ mounts the page without any. */
export type Graph3dPageProps = Omit<LazyCanvasProps, 'paused'>

export function Graph3dPage(props: Graph3dPageProps) {
  return (
    <section className="graph3d">
      <title>Grafo 3D · My Story Marker</title>
      <div className="graph3d-head">
        <Heading>Grafo 3D</Heading>
        <p className="graph3d-lead">Vista decorativa: el grafo de la novela todavía no se dibuja aquí.</p>
      </div>
      <PlanetHero className="graph3d-hero" {...props} />
    </section>
  )
}
