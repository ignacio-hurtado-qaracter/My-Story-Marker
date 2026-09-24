// The decorative orange planet with its pause toggle: the lazily loaded canvas and the
// "Pausar animación" button, in one place. Spec 003, FR-3D-03..05 (plan 003 Q8): /graph3d
// mounts it under its heading, and the cover mounts it as main's hero (FR-COVER-01), through
// graph3d/index.ts. three.js stays in LazyCanvas's lazy chunk (spec 002, NFR-01, AC 12).
//
// States come from LazyCanvas: loading is its text fallback, error its panel (WebGL missing, or
// the chunk failing), loaded the planet. A `decorative` hero (the cover) replaces the WebGL
// error with a still, CSS-drawn planet and no toggle: nothing moves, so there is nothing to
// pause, and a reader of the cover is not told about a 3D view they never asked for.
import { useState } from 'react'

import './graph3d.css'
import { isWebGLAvailable, LazyCanvas, type LazyCanvasProps } from './LazyCanvas'
import { useReducedMotion } from './useReducedMotion'

export interface PlanetHeroProps {
  /** Extra classes for the wrapper, so each page sizes and frames the planet its own way. */
  className?: string
  /** True where the planet is only decoration (the cover): without WebGL it degrades to a still picture. */
  decorative?: boolean
  /** Test seam (spec 002, AC 18; spec 003, AC 7): the scene, normally the lazily loaded planet. */
  scene?: LazyCanvasProps['scene']
  /** Test seam: whether WebGL is available. Defaults to LazyCanvas's check. */
  webglAvailable?: () => boolean
}

export function PlanetHero({
  className,
  decorative = false,
  scene,
  webglAvailable = isWebGLAvailable,
}: PlanetHeroProps) {
  // FR-3D-04: under reduced motion the planet starts paused; the toggle decides after that.
  const reducedMotion = useReducedMotion()
  const [paused, setPaused] = useState(() => reducedMotion)
  const wrapperClass = className === undefined ? 'planet-hero' : `planet-hero ${className}`

  if (decorative && !webglAvailable()) {
    return (
      <div className={`${wrapperClass} planet-hero-still`}>
        <div className="planet-hero-stage">
          <div className="planet-still" aria-hidden="true" />
        </div>
      </div>
    )
  }

  return (
    <div className={wrapperClass}>
      <div className="planet-hero-stage">
        <LazyCanvas
          paused={paused}
          webglAvailable={webglAvailable}
          {...(scene === undefined ? {} : { scene })}
        />
      </div>
      {/* WAI-ARIA toggle button: a constant label, with the state in aria-pressed. It sits
          outside the canvas, which is aria-hidden (WCAG 2.2.2). */}
      <button
        type="button"
        className="btn-ghost planet-hero-toggle"
        aria-pressed={paused}
        onClick={() => {
          setPaused((value) => !value)
        }}
      >
        Pausar animación
      </button>
    </div>
  )
}
