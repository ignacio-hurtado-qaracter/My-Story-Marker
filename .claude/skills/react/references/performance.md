# Performance

Guidance from the official react-three-fiber performance and pitfalls pages, plus the React
Compiler's effect on ordinary component code.

## Render only when something changed

```tsx
<Canvas frameloop="demand">
```

On demand, frames are rendered when prop changes are detected in the component tree. When
you mutate something React does not know about, call `invalidate()` from `useThree` to
request a frame. It sets a flag rather than rendering immediately.

When starting an animation under `demand`, request the frame pre-emptively, inside a
`requestAnimationFrame`, or the first frame arrives late and the motion visibly jumps.

For a view like an entity graph that sits still until the user moves the camera, this is the
single largest saving available.

## Draw calls

Use `InstancedMesh`, or drei's `Instances`, to collapse many identical objects into one draw
call. The official guidance on ordinary meshes is blunt: no more than about a thousand as an
absolute maximum.

Reuse geometries and materials rather than creating one per object. Each one is overhead on
the GPU. Hoist them to module scope or memoise them.

Assets loaded through `useLoader` are cached by URL, so never load the same texture or model
once per instance.

## Avoid re-renders

Never set state inside `useFrame` or any other loop. Mutate refs.

Do not subscribe a component to a fast-changing store value. Read it imperatively inside the
frame callback instead.

Do not mount and unmount pieces of the scene to show and hide them. Materials and geometries
are recompiled on remount, which is expensive. Toggle visibility:

```tsx
<GraphLayer visible={layer === 'entities'} />
```

## Allocation

Do not allocate objects per frame. A `new THREE.Vector3()` inside `useFrame` runs sixty
times a second and feeds the garbage collector. Reuse a module-scope vector:

```tsx
const v = new THREE.Vector3()
useFrame(() => { v.set(x, y, z); ref.current.position.copy(v) })
```

## Degrading gracefully

`dpr` defaults to `[1, 2]`, which already clamps the pixel ratio on high density displays.

For heavier scenes, `<Canvas performance={{ min: ... }}>` plus `regress()` during
interaction lets you drop resolution or effects while the user is moving and restore quality
when they stop. Read `state.performance.current` to react to it. drei's `AdaptiveDpr` and
`AdaptiveEvents` automate the common case.

drei's `<Detailed />` swaps in lower resolution geometry with distance, which matters for a
graph or a location hierarchy with many distant nodes.

Use `startTransition` to spread heavy scene construction across frames rather than blocking
one long frame.

## Ordinary React performance

With the React Compiler enabled, do not scatter `useMemo`, `useCallback` and `React.memo`
through the code. The compiler memoises from its own analysis, and the official position is
that the result is usually at least as precise as hand-written memoisation.

Use them as a deliberate escape hatch when you need control over exactly what is memoised,
and say so in a comment. In existing code that already has manual memoisation, leave it
alone unless you are testing the change, because removing it alters what the compiler
produces.

The compiler depends on code following the Rules of React. A component that mutates props or
state during render is not only buggy, it is uncompilable. Enable the compiler-aware lint
rules from `eslint-plugin-react-hooks`, including `set-state-in-render`, `set-state-in-effect`
and `refs`.

## Payload size

Scenes, dossiers and assembled contexts can be large. Two habits keep the interface
responsive: request only the fields a view needs, and render progressively rather than
waiting for a whole payload. A manuscript scene is prose, and prose streams well.
