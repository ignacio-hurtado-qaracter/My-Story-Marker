// The /graph3d page: a heading, a pause toggle and the lazily loaded decorative planet, in
// main's hero look. Spec 002, FR-3D-01; spec 003, FR-3D-03..05.
// Loading, error and loaded states come from LazyCanvas; empty does not apply, since the page
// shows no data.
import { useState } from 'react'

import { Heading } from '../shared/ui'
import './graph3d.css'
import { LazyCanvas, type LazyCanvasProps } from './LazyCanvas'
import { useReducedMotion } from './useReducedMotion'

/** The props exist for the tests (AC 18; spec 003, AC 7); app/ mounts the page without any. */
export type Graph3dPageProps = Omit<LazyCanvasProps, 'paused'>

export function Graph3dPage(props: Graph3dPageProps) {
  // FR-3D-04: under reduced motion the planet starts paused; the toggle decides after that.
  const reducedMotion = useReducedMotion()
  const [paused, setPaused] = useState(() => reducedMotion)

  return (
    <section className="graph3d">
      <div className="graph3d-head">
        <div>
          <Heading>Grafo 3D</Heading>
          <p className="graph3d-lead">Vista decorativa: el grafo de la novela todavía no se dibuja aquí.</p>
        </div>
        {/* WAI-ARIA toggle button: a constant label, with the state in aria-pressed. It sits
            outside the canvas, which is aria-hidden (WCAG 2.2.2). */}
        <button
          type="button"
          className="btn-ghost graph3d-toggle"
          aria-pressed={paused}
          onClick={() => {
            setPaused((value) => !value)
          }}
        >
          Pausar animación
        </button>
      </div>
      <div className="graph3d-stage">
        <LazyCanvas {...props} paused={paused} />
      </div>
    </section>
  )
}
