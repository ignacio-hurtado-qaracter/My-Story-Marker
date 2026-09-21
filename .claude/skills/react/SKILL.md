---
name: react
description: React 19 and three.js conventions for this project's frontend. Use for code under frontend/: components, hooks, effects, state, data fetching, and 3D views with react-three-fiber.
---

# React

Conventions for `frontend/` in this repository: React 19 with three.js, talking to the
FastAPI backend over its API. Written against the official React and react-three-fiber
documentation. This skill is owned by this repository, not by the React project.

Pinned versions this was written against:

| Package | Version |
|---|---|
| `react`, `react-dom` | 19.3.0 |
| `three` | 0.186.0 |
| `@react-three/fiber` | 9.7.0 |
| `@react-three/drei` | 10.7.8 |

`@react-three/fiber` major versions are bound to React major versions: v8 pairs with React
18, **v9 pairs with React 19**. Do not mix them.

## Quick reference

* Pass `ref` as an ordinary prop. Do not write `forwardRef` in new code.
* Never call `setState` inside `useFrame`. Mutate refs instead. See [three.js](references/three-js.md).
* Before writing a `useEffect`, check it against the list in [hooks and effects](references/hooks-and-effects.md). Most effects are a mistake.
* Derive values during render. Do not mirror props into state.
* Reach for the React Compiler rather than hand-written `useMemo`/`useCallback`.
* The frontend never touches the harness stores. It calls the backend API and nothing else.
* Types for API responses are generated from the backend's OpenAPI schema. Never hand-write them.

## The three rules everything else follows from

**Components and hooks are pure.** The same props, state and context must produce the same
output. React may render a component many times before committing, so a render that
mutates something observable is a bug even when it appears to work.

**Side effects go in event handlers first.** An effect is the last resort, not the default.
The test from the official docs: if the logic runs because of a particular interaction it
belongs in the handler; only if it runs because the component appeared on screen does it
belong in an effect.

**Props, state and hook arguments are immutable.** They are a snapshot for one render. Once
a value has been passed to a hook or rendered into JSX, do not modify it.

Hooks are called unconditionally at the top level, before any early return, and only from
components or other hooks. The one exception is `use`, which may be called conditionally.

## React 19, in this project

**`ref` is a prop.** Function components accept `ref` directly. `forwardRef` still works and
is not yet removed, but the official docs state it is no longer necessary and will be
deprecated. New code passes `ref` through like any other prop.

**Ref callbacks may return a cleanup function**, which runs on unmount. A consequence worth
knowing: an arrow ref callback with an implicit return is now a type error. Use a block
body.

```tsx
<div ref={(el) => { nodeRef.current = el }} />
```

**`propTypes` and `defaultProps` are removed for function components.** Use TypeScript for
the contract and ES default parameters for the values.

**Render `<Context>` directly**, not `<Context.Provider>`.

**`use` reads a promise or a context** and may appear after an early return or inside a
condition. Promises handed to `use` must come from a cache that survives re-renders, never
be created during render. In practice, in this project, fetching goes through the generated
API client and a query cache rather than through bare `use`.

**Document metadata hoists.** A `<title>` or `<meta>` rendered anywhere in the tree is moved
into `<head>`, so a scene view can own its own title without a separate head manager.

Actions, `useActionState`, `useFormStatus` and `useOptimistic` are available. They matter
for the editing surfaces that write back to the backend: a promotion ruling, a violation
resolution, an edit to a scene record. `useOptimistic` reverts automatically when the
action fails, which is the behaviour you want when the backend rejects a write that would
have breached a permission boundary.

## Memoisation and the React Compiler

React Compiler 1.0 is stable and the official recommendation for new applications. It
memoises automatically from its own analysis, and the docs state the result is usually at
least as precise as hand-written memoisation.

For this project:

* Enable the compiler, and enable the compiler-aware lint rules from
  `eslint-plugin-react-hooks` (`set-state-in-render`, `set-state-in-effect`, `refs`).
* Do not add `useMemo`, `useCallback` or `React.memo` by reflex. Add them only as a
  deliberate escape hatch, with a comment saying what you are controlling.
* The compiler only works on code that follows the Rules of React. A component that mutates
  during render does not merely risk a bug, it defeats the compiler.

## Data from the backend

The backend is the only process that reads the stores. Everything the frontend shows is
fetched.

* Response types come from the generated OpenAPI client. If a route changes, the client is
  regenerated in the same change. Continuous integration fails on a stale client.
* Do not fetch in a bare `useEffect`. If you must, the effect needs a cleanup that ignores
  stale responses, or a fast reply will overwrite a slow one from an earlier render.
* Server state and UI state are different things. Cache the first, keep the second local.
* An assembled context or a manuscript scene can be large. Render it progressively rather
  than blocking the view on the whole payload.

## 3D views

The three.js work in this project visualises the entity graph, the timeline and the
location hierarchy. All of it goes through react-three-fiber. Never construct a `Scene` or
a `WebGLRenderer` by hand alongside React.

The rules that actually cause bugs are in [three.js](references/three-js.md), and the
performance guidance is in [performance](references/performance.md). The single most
important one: `useFrame` runs sixty times a second, so anything that triggers a React
render inside it will destroy the frame rate.

## References

* [Hooks and effects](references/hooks-and-effects.md) — when an effect is legitimate, and the named anti-patterns.
* [three.js](references/three-js.md) — `Canvas`, `useFrame`, `useThree`, `useLoader`, disposal, drei.
* [Performance](references/performance.md) — on-demand rendering, instancing, allocation, re-render avoidance.
