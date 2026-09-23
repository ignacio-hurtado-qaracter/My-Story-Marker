// The 3D canvas behind React.lazy and Suspense. Spec 002, FR-3D-01 and FR-3D-02 (it lives in
// graph3d/, not shared/three/, because graph3d/ is its only user).
//
// States: loading is the text fallback while the three.js chunk arrives; error is the shared
// ErrorPanel, when WebGL is unavailable (checked before the chunk is requested) or the chunk
// fails to load (AC 18); loaded is the scene. The scene and the WebGL check are props so the
// tests can inject them: jsdom has no WebGL.
import { Component, lazy, Suspense, type ComponentType, type ReactNode } from 'react'

import { ErrorPanel } from '../shared/ui'

// The only reference to EmptyScene in graph3d/, and it is dynamic (NFR-01). Created once, at
// module load: a lazy component created during render would remount, and request the chunk
// again, on every render.
const LazyEmptyScene = lazy(() => import('./EmptyScene').then((module) => ({ default: module.EmptyScene })))

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
  /**
   * The scene, normally a React.lazy component so that rendering it requests its chunk.
   * Defaults to the lazily imported EmptyScene; tests pass a lazy stub.
   */
  scene?: ComponentType
  /** Reports whether WebGL is available. Defaults to isWebGLAvailable. */
  webglAvailable?: () => boolean
}

export function LazyCanvas({ scene: Scene = LazyEmptyScene, webglAvailable = isWebGLAvailable }: LazyCanvasProps) {
  if (!webglAvailable()) {
    return <ErrorPanel message="Tu navegador no admite WebGL, que la vista 3D necesita." />
  }
  return (
    <ChunkErrorBoundary>
      <Suspense fallback={<p role="status">Cargando vista 3D…</p>}>
        <Scene />
      </Suspense>
    </ChunkErrorBoundary>
  )
}
