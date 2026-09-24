// The /graph3d page: a heading and the lazily loaded empty scene. Spec 002, FR-3D-01.
// Loading, error and loaded states come from LazyCanvas; empty does not apply, since the page
// shows no data.
import { Heading } from '../shared/ui'
import { LazyCanvas, type LazyCanvasProps } from './LazyCanvas'

/** The props exist for the tests (AC 18); app/ mounts the page without any. */
export type Graph3dPageProps = LazyCanvasProps

export function Graph3dPage(props: Graph3dPageProps) {
  return (
    <section>
      <Heading>Grafo 3D</Heading>
      <LazyCanvas {...props} />
    </section>
  )
}
