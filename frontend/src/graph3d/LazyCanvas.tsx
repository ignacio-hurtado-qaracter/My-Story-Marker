// The 3D canvas behind React.lazy and Suspense. Spec 002, FR-3D-01 and FR-3D-02 (it lives in
// graph3d/, not shared/three/, because graph3d/ is its only user); the scene is spec 003's
// planet (FR-3D-03), which receives the page's `paused` flag (FR-3D-04, FR-3D-05).
//
// States: loading is the text fallback while the three.js chunk arrives; error is the shared
// ErrorPanel, when WebGL is unavailable (checked before the chunk is requested) or the chunk
// fails to load (AC 18); loaded is the scene. The scene and the WebGL check are props so the
// tests can inject them: jsdom has no WebGL.
import { Component, lazy, Suspense, type ComponentType, type ReactNode } from 'react'

import { ErrorPanel } from '../shared/ui'

// The only reference to PlanetScene in graph3d/, and it is dynamic (NFR-01), so its chunk is
// named PlanetScene-*.js. Created once, at module load: a lazy component created during render
// would remount, and request the chunk again, on every render.
const LazyPlanetScene = lazy(() => import('./PlanetScene').then((module) => ({ default: module.PlanetScene })))

let webglAvailableCache: boolean | undefined

/** True when the browser can create a WebGL context. Checked once, then remembered. */
export function isWebGLAvailable(): boolean {
  if (webglAvailableCache === undefined) {
    try {
      const canvas = document.createElement('canvas')
      const context = canvas.getContext('webgl2') ?? canvas.getContext('webgl')
      webglAvailableCache = context !== null
      // Release the probe context now instead of waiting for garbage collection.
      context?.getExtension('WEBGL_lose_context')?.loseContext()
    } catch {
      webglAvailableCache = false
    }
  }
  return webglAvailableCache
}

interface ChunkErrorBoundaryProps {
  children: ReactNode
}

interface ChunkErrorBoundaryState {
  failed: boolean
}

/** Shows the error panel when the scene's chunk fails to load (or the scene throws). */
class ChunkErrorBoundary extends Component<ChunkErrorBoundaryProps, ChunkErrorBoundaryState> {
  override state: ChunkErrorBoundaryState = { failed: false }

  static getDerivedStateFromError(): ChunkErrorBoundaryState {
    return { failed: true }
  }

  override render() {
    // No retry: React.lazy caches the rejected import, so retrying in place cannot succeed;
    // reloading the page can.
    return this.state.failed ? <ErrorPanel message="No se pudo cargar la vista 3D." /> : this.props.children
  }
}

export interface LazyCanvasProps {
  /** True while the scene's animation is paused; forwarded to the scene (spec 003, FR-3D-04). */
  paused: boolean
  /**
   * The scene, normally a React.lazy component so that rendering it requests its chunk.
   * Defaults to the lazily imported PlanetScene; tests pass a lazy stub (spec 003, FR-3D-05).
   */
  scene?: ComponentType<{ paused: boolean }>
  /** Reports whether WebGL is available. Defaults to isWebGLAvailable. */
  webglAvailable?: () => boolean
}

export function LazyCanvas({
  paused,
  scene: Scene = LazyPlanetScene,
  webglAvailable = isWebGLAvailable,
}: LazyCanvasProps) {
  if (!webglAvailable()) {
    return <ErrorPanel message="Tu navegador no admite WebGL, que la vista 3D necesita." />
  }
  return (
    <ChunkErrorBoundary>
      <Suspense fallback={<p role="status">Cargando vista 3D…</p>}>
        <Scene paused={paused} />
      </Suspense>
    </ChunkErrorBoundary>
  )
}
