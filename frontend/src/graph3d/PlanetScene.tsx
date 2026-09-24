// The orange planet on /graph3d: main's hero composition, ported declaratively to
// react-three-fiber. Spec 003, FR-3D-03 and FR-3D-04 (it replaces spec 002's empty scene).
//
// This is the only module that imports three.js at the top level, and it is reached only
// through the dynamic import in LazyCanvas, so three.js lands in its own chunk and never in the
// initial JavaScript for /scenes (spec 002, NFR-01 and AC 12). Nothing may import this file
// statically.
//
// Decorative: no controls and no pointer interaction; the wrapper carries aria-hidden, since
// the page's heading and pause toggle carry the meaning.
import { Canvas, useFrame } from '@react-three/fiber'
import { useEffect, useRef, type RefObject } from 'react'
import type { Mesh, Points } from 'three'

// main's palette (spec 003, FR-TOK-01), as literals: three.js cannot read CSS custom properties.
const ORANGE = '#FF7A2F'
const ORANGE_DARK = '#E5661F'
const INK = '#1E2B37'
const RIM = '#ffd9c2'

const TAU = Math.PI * 2

/** Longest step the animation clock takes, in seconds, so a background tab does not jump. */
const MAX_DELTA = 0.1

/**
 * mulberry32: a small seeded generator. Randomness is drawn once, at module load, so render
 * stays pure and the same planet appears on every visit.
 */
function mulberry32(seed: number): () => number {
  let state = seed
  return () => {
    state = (state + 0x6d2b79f5) | 0
    let t = Math.imul(state ^ (state >>> 15), state | 1)
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61)
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296
  }
}

const random = mulberry32(0x2f7a)

interface Ring {
  radius: number
  tilt: number
  speed: number
  /** Where the ring's satellite starts, in radians. */
  phase: number
}

const RINGS: readonly Ring[] = [
  { radius: 2.9, tilt: 0.45, speed: 0.35 },
  { radius: 3.6, tilt: -0.7, speed: -0.22 },
  { radius: 4.4, tilt: 1.1, speed: 0.15 },
].map((ring) => ({ ...ring, phase: random() * TAU }))

const PARTICLE_COUNT = 900

/** A flattened shell of particles around the planet, radius 2.4 to 7.9, as in main. */
const PARTICLE_POSITIONS = new Float32Array(PARTICLE_COUNT * 3)
for (let i = 0; i < PARTICLE_COUNT; i++) {
  const radius = 2.4 + random() * 5.5
  const theta = random() * TAU
  const phi = Math.acos(2 * random() - 1)
  PARTICLE_POSITIONS.set(
    [
      radius * Math.sin(phi) * Math.cos(theta),
      radius * Math.sin(phi) * Math.sin(theta) * 0.55,
      radius * Math.cos(phi),
    ],
    i * 3,
  )
}

type PausedRef = RefObject<boolean>

/**
 * Runs `step` on every frame while playing, with this component's own animation time. While
 * paused the callback returns at once and the time stands still, so resuming continues where
 * the animation stopped. The delta is clamped (MAX_DELTA).
 */
function useAnimation(paused: PausedRef, step: (time: number) => void): void {
  const time = useRef(0)
  useFrame((_state, delta) => {
    if (paused.current) return
    time.current += Math.min(delta, MAX_DELTA)
    step(time.current)
  })
}

interface AnimatedProps {
  paused: PausedRef
}

/**
 * One tilted orbit ring and its satellite. The satellite is a child of the ring, so moving it
 * along the ring's own plane needs no scratch vector (main applies the ring's rotation by hand).
 */
function OrbitRing({ ring, paused }: AnimatedProps & { ring: Ring }) {
  const torus = useRef<Mesh>(null)
  const satellite = useRef<Mesh>(null)

  useAnimation(paused, (time) => {
    if (torus.current !== null) torus.current.rotation.z = time * ring.speed * 0.2
    const angle = ring.phase + time * ring.speed * 1.6
    satellite.current?.position.set(Math.cos(angle) * ring.radius, Math.sin(angle) * ring.radius, 0)
  })

  return (
    <mesh ref={torus} rotation-x={Math.PI / 2 + ring.tilt}>
      <torusGeometry args={[ring.radius, 0.012, 8, 160]} />
      <meshBasicMaterial color={INK} transparent opacity={0.18} />
      {/* The starting position is time 0, so a scene that starts paused still shows it. */}
      <mesh ref={satellite} position={[Math.cos(ring.phase) * ring.radius, Math.sin(ring.phase) * ring.radius, 0]}>
        <sphereGeometry args={[0.09, 16, 16]} />
        <meshStandardMaterial color={INK} roughness={0.4} />
      </mesh>
    </mesh>
  )
}

/** The planet: a solid core, a wireframe shell, the orbit rings and the particle field. */
function Planet({ paused }: AnimatedProps) {
  const core = useRef<Mesh>(null)
  const shell = useRef<Mesh>(null)
  const particles = useRef<Points>(null)

  useAnimation(paused, (time) => {
    if (core.current !== null) {
      core.current.rotation.y = time * 0.12
      core.current.rotation.x = Math.sin(time * 0.1) * 0.15
    }
    if (shell.current !== null) {
      shell.current.rotation.y = -time * 0.08
      shell.current.rotation.z = time * 0.05
    }
    if (particles.current !== null) particles.current.rotation.y = time * 0.03
  })

  return (
    <group>
      <mesh ref={core}>
        <icosahedronGeometry args={[1.5, 2]} />
        <meshStandardMaterial color={ORANGE} roughness={0.55} metalness={0.05} flatShading />
      </mesh>
      <mesh ref={shell}>
        <icosahedronGeometry args={[1.95, 1]} />
        <meshBasicMaterial color={ORANGE_DARK} wireframe transparent opacity={0.35} />
      </mesh>
      {RINGS.map((ring) => (
        <OrbitRing key={ring.radius} ring={ring} paused={paused} />
      ))}
      <points ref={particles}>
        <bufferGeometry>
          <bufferAttribute attach="attributes-position" args={[PARTICLE_POSITIONS, 3]} />
        </bufferGeometry>
        <pointsMaterial color={ORANGE_DARK} size={0.045} transparent opacity={0.7} sizeAttenuation />
      </points>
    </group>
  )
}

export interface PlanetSceneProps {
  /** True while the animation is paused (the page's toggle, or reduced motion). */
  paused: boolean
}

export function PlanetScene({ paused }: PlanetSceneProps) {
  // useFrame callbacks read the flag through a ref, never through React state (FR-3D-04).
  const pausedRef = useRef(paused)
  useEffect(() => {
    pausedRef.current = paused
  }, [paused])

  // As main's hero: on narrow screens the camera steps back so the outer ring stays in frame.
  // Read once at mount; the Canvas takes its camera only then.
  const cameraZ = window.innerWidth < 600 ? 12 : 9

  return (
    <div className="planet-canvas" aria-hidden="true">
      {/* `demand` while paused: no frame is drawn until something invalidates the canvas.
          `flat`: no tone mapping, so the orange matches main's renderer. */}
      <Canvas flat frameloop={paused ? 'demand' : 'always'} camera={{ position: [0, 0.6, cameraZ], fov: 45, near: 0.1, far: 100 }}>
        <ambientLight intensity={0.9} />
        <directionalLight position={[4, 5, 6]} intensity={1.4} />
        <directionalLight position={[-5, -2, -4]} intensity={0.6} color={RIM} />
        <Planet paused={pausedRef} />
      </Canvas>
    </div>
  )
}
