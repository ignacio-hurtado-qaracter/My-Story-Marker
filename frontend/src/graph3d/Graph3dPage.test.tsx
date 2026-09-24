// The /graph3d states: spec 002, FR-3D-01 and AC 18; the pause toggle and reduced motion:
// spec 003, FR-3D-04 and AC 7. The scene and the WebGL check are injected: jsdom has no WebGL,
// so no test here mounts real three.js (that is AC 13's Playwright run). Each scene is a
// React.lazy stub, so its loader stands in for the dynamic import of the three.js chunk.
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { lazy, type ComponentType } from 'react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { Graph3dPage } from './Graph3dPage'

interface SceneModule {
  default: ComponentType
}

function StubScene() {
  return <p>Escena de prueba</p>
}

const webglOn = () => true

/** A stub scene that shows the `paused` flag it receives (spec 003, AC 7). */
function PausedProbe({ paused }: { paused: boolean }) {
  return <p>{`paused=${String(paused)}`}</p>
}

function probeScene() {
  return lazy(() => Promise.resolve({ default: PausedProbe }))
}

/** Replaces window.matchMedia with one that reports `prefers-reduced-motion: reduce` or not. */
function stubReducedMotion(reduce: boolean) {
  vi.stubGlobal(
    'matchMedia',
    (query: string): MediaQueryList => ({
      matches: reduce && query === '(prefers-reduced-motion: reduce)',
      media: query,
      onchange: null,
      addEventListener: () => {},
      removeEventListener: () => {},
      addListener: () => {},
      removeListener: () => {},
      dispatchEvent: () => false,
    }),
  )
}

function toggle() {
  return screen.getByRole('button', { name: 'Pausar animación' })
}

describe('Graph3dPage', () => {
  // spec 002 / AC 18
  it('shows the error panel when the three.js chunk fails to load', async () => {
    // React reports an error caught by a boundary on console.error; here it is expected.
    const consoleError = vi.spyOn(console, 'error').mockImplementation(() => {})
    const scene = lazy(() => Promise.reject<SceneModule>(new Error('chunk failed')))

    render(<Graph3dPage scene={scene} webglAvailable={webglOn} />)

    expect(await screen.findByRole('alert')).toHaveTextContent('No se pudo cargar la vista 3D.')
    expect(screen.getByRole('heading', { level: 1, name: 'Grafo 3D' })).toBeInTheDocument()
    consoleError.mockRestore()
  })

  // spec 002 / AC 18
  it('shows the error panel, and never requests the chunk, when WebGL is unavailable', () => {
    const load = vi.fn(() => Promise.resolve<SceneModule>({ default: StubScene }))

    render(<Graph3dPage scene={lazy(load)} webglAvailable={() => false} />)

    expect(screen.getByRole('alert')).toHaveTextContent('WebGL')
    expect(load).not.toHaveBeenCalled()
    expect(screen.queryByText('Cargando vista 3D…')).not.toBeInTheDocument()
  })

  // spec 002 / AC 18
  it('renders the scene once the chunk has loaded', async () => {
    const scene = lazy(() => Promise.resolve<SceneModule>({ default: StubScene }))

    render(<Graph3dPage scene={scene} webglAvailable={webglOn} />)

    expect(await screen.findByText('Escena de prueba')).toBeInTheDocument()
    expect(screen.queryByRole('alert')).not.toBeInTheDocument()
  })

  // spec 002 / AC 18
  it('shows the text fallback while the chunk is on its way', () => {
    const scene = lazy(() => new Promise<SceneModule>(() => {}))

    render(<Graph3dPage scene={scene} webglAvailable={webglOn} />)

    expect(screen.getByRole('status')).toHaveTextContent('Cargando vista 3D…')
    expect(screen.queryByRole('alert')).not.toBeInTheDocument()
  })

  describe('pause toggle and reduced motion', () => {
    afterEach(() => {
      vi.unstubAllGlobals()
    })

    // spec 003 / AC 7
    it('starts playing, with the toggle not pressed', async () => {
      stubReducedMotion(false)

      render(<Graph3dPage scene={probeScene()} webglAvailable={webglOn} />)

      expect(await screen.findByText('paused=false')).toBeInTheDocument()
      expect(toggle()).toHaveAttribute('aria-pressed', 'false')
    })

    // spec 003 / AC 7
    it('pauses the scene when the toggle is pressed, keeping its label', async () => {
      stubReducedMotion(false)
      render(<Graph3dPage scene={probeScene()} webglAvailable={webglOn} />)
      await screen.findByText('paused=false')

      await userEvent.click(toggle())

      expect(screen.getByText('paused=true')).toBeInTheDocument()
      expect(toggle()).toHaveAttribute('aria-pressed', 'true')
      expect(toggle()).toHaveTextContent(/^Pausar animación$/)
    })

    // spec 003 / AC 7
    it('starts paused under prefers-reduced-motion: reduce', async () => {
      stubReducedMotion(true)

      render(<Graph3dPage scene={probeScene()} webglAvailable={webglOn} />)

      expect(await screen.findByText('paused=true')).toBeInTheDocument()
      expect(toggle()).toHaveAttribute('aria-pressed', 'true')
    })

    // spec 003 / AC 7
    it('still renders, playing, when matchMedia does not exist', async () => {
      vi.stubGlobal('matchMedia', undefined)

      render(<Graph3dPage scene={probeScene()} webglAvailable={webglOn} />)

      expect(screen.getByRole('heading', { level: 1, name: 'Grafo 3D' })).toBeInTheDocument()
      expect(await screen.findByText('paused=false')).toBeInTheDocument()
      expect(toggle()).toHaveAttribute('aria-pressed', 'false')
    })
  })
})
