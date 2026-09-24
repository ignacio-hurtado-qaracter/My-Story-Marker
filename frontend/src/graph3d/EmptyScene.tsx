// The empty 3D scene on /graph3d: camera, light and orbit controls, nothing else. Spec 002,
// FR-3D-01. This is the only module that imports three.js at the top level, and it is reached
// only through the dynamic import in LazyCanvas, so three.js lands in its own chunk and never
// in the initial JavaScript for /scenes (NFR-01, AC 12). Nothing may import this file
// statically.
import { OrbitControls } from '@react-three/drei'
import { Canvas } from '@react-three/fiber'

export function EmptyScene() {
  return (
    // `demand`: an empty scene only needs a frame when the camera moves; drei's OrbitControls
    // requests one on every change.
    <Canvas
      frameloop="demand"
      camera={{ position: [6, 4, 8], fov: 50 }}
      style={{ height: '70vh' }}
      fallback={<p>Vista 3D vacía.</p>}
    >
      <ambientLight intensity={0.5} />
      <directionalLight position={[5, 10, 5]} intensity={1} />
      <gridHelper args={[10, 10]} />
      <OrbitControls makeDefault />
    </Canvas>
  )
}
