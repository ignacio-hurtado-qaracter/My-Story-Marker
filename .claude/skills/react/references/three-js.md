# three.js through react-three-fiber

react-three-fiber is a React renderer for three.js. It expresses three.js in JSX rather
than wrapping it, so anything that works in three.js works here. Components render outside
React, so there is no per-frame React overhead when you follow the rules below.

**Version pairing is strict.** `@react-three/fiber` v8 pairs with React 18 and v9 pairs with
React 19. This project uses React 19, so fiber v9. Install `three`, `@react-three/fiber`
and `@types/three`.

## `<Canvas>`

The entry point. By default it creates a perspective camera at `[0, 0, 5]` with a field of
view of 75, a scene, a WebGL renderer with antialiasing and alpha, sRGB output and ACES
Filmic tone mapping, and a raycaster. It resizes with its container automatically.

Props worth knowing: `frameloop` (`always` by default, `demand`, `never`), `dpr` (defaults
to `[1, 2]`), `shadows` (off by default), `camera`, `gl`, `performance`, `flat`, `linear`
and `events`.

Everything three.js related lives inside the canvas. Do not construct a `Scene` or a
`WebGLRenderer` by hand next to React.

## `useThree`

Returns the renderer state: `gl`, `scene`, `camera`, `raycaster`, `pointer`, `clock`,
`size`, `viewport`, plus `set`, `get`, `invalidate`, `setSize` and `setFrameloop`.

Reading it during render subscribes the component to changes in those values. In a
component that runs per frame, prefer reading what you need once rather than subscribing to
values that change constantly.

## `useFrame`

```tsx
useFrame((state, delta) => {
  meshRef.current.rotation.y += delta * 0.5
})
```

**Never call `setState` inside `useFrame`.** This is the rule that matters most. The
callback runs on every frame, so a state update there re-renders the React tree sixty times
a second. Mutate refs instead.

Use `delta` rather than a fixed increment, so motion does not depend on the display's
refresh rate.

For state that lives in an external store, read it imperatively inside the callback rather
than subscribing the component to it:

```tsx
useFrame(() => { ref.current.position.x = store.getState().x })
```

A non-zero `renderPriority` takes over the render loop, and you then have to call
`state.gl.render(...)` yourself. Callbacks run in ascending priority order. Negative values
let you sequence work without taking over the loop.

## `useLoader`

Loads three.js assets and suspends, so wrap the consumer in `<Suspense>`. Results are
cached, with the URL as the cache key, so the same asset loaded in a hundred components is
fetched once. It accepts an array of URLs for parallel loading, and `useLoader.preload()`
prefetches.

`useGraph(object3d)` builds a memoised, named collection of objects and materials from any
`Object3D`, which is the convenient way to pick pieces out of a loaded model.

## Disposal

react-three-fiber calls `object.dispose()` on unmounted objects when the method exists, and
detaches `attach` bindings automatically. You usually do not manage this yourself.

Opt out with `dispose={null}`, on an element or on a parent to cover the whole subtree, when
you cache or reuse assets and do not want them freed on unmount.

Changing `args` reconstructs the object from scratch. Treat `args` as a constructor
signature, not as a place for animated values.

## drei

`@react-three/drei` is the official helper collection for react-three-fiber. It builds on
`three-stdlib` rather than `three/examples/jsm`.

What is likely to matter for this project's views:

- **Controls**: `OrbitControls`, `CameraControls`, `ScrollControls`, `KeyboardControls`.
- **Loaders**: `useGLTF`, `useTexture`, `useFont`.
- **Misc**: `Html` for anchoring DOM to a 3D position, which is how a node in the entity
  graph gets a readable label. `Stats` for a frame counter during development.
- **Performance**: `Instances`, `Merged`, `Points`, `AdaptiveDpr`, `Preload`.
- **Staging**: `Environment`, `ContactShadows`, `Stage`.
- **Shapes**: `Line`, `RoundedBox`. `Line` is the practical way to draw graph edges.
- **Portals**: `View` renders several independent views into one canvas, which is how a
  timeline and a graph can share a renderer.

## Applying this to the project's views

The entity graph, the timeline and the location hierarchy are all many small objects with
labels. That shape has a known answer: instance the repeated geometry, draw edges with
`Line`, attach labels with `Html` only for what is near the camera, and keep the whole thing
on `frameloop="demand"` so an idle graph costs nothing.
