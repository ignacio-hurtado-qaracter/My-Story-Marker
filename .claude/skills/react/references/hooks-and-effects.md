# Hooks and effects

## Rules of hooks

Call hooks at the top level of a component or of another hook. Never inside a loop, a
condition, a nested function, or after an early return. Never call a hook from a plain
JavaScript function.

`use` is the single exception: it may be called conditionally and after an early return.

Components are used in JSX, never called as functions. Hooks are not values to pass around.

## Effects are the last resort

The official decision rule: **use an effect only for code that should run because the
component was displayed to the user.** If the logic happens because of a particular
interaction, it belongs in the event handler.

Applied to this project: saving a canon ruling belongs in the handler of the button that
made the ruling. Opening a connection to stream a draft belongs in an effect, because it
exists as long as the view is on screen.

## When an effect is legitimate

Effects exist to synchronise with systems outside React.

- **A non-React system**: a three.js control that is not wrapped by react-three-fiber, a
  browser API, an observer, a timer, a network connection held open for streaming.
- **Data fetching driven by props or state**, but only with a cleanup that ignores stale
  responses. Without it, a fast reply to a later request is overwritten by a slow reply to
  an earlier one. Prefer the query cache over hand-written fetching effects.
- **Subscribing to an external store**, where `useSyncExternalStore` is the correct tool
  rather than a hand-written effect.

```tsx
useEffect(() => {
  let ignore = false
  api.getScene(sceneId).then((data) => {
    if (!ignore) setScene(data)
  })
  return () => { ignore = true }
}, [sceneId])
```

## The anti-patterns, named

Each of these is documented as a case where an effect is the wrong tool.

1. **Transforming data for rendering.** Calculate it during render.
2. **Updating state from props or state.** That state is redundant. Derive it.
3. **Caching an expensive calculation.** Use `useMemo`, not state plus an effect.
4. **Resetting all state when a prop changes.** Pass a `key` and let React remount.
5. **Adjusting some state when a prop changes.** Compute during render. Setting state
   during render is the documented escape hatch here.
6. **Event-specific logic.** It belongs in the handler that caused it.
7. **Sharing logic between two handlers.** Extract a function and call it from both.
8. **Chains of computations**, where an effect sets state that triggers another effect.
   Each link adds a render pass and the chain is fragile.
9. **Notifying a parent about a state change.** Update both in the same event handler.
10. **Passing data up to a parent.** Data flows down. Let the parent own the state.
11. **Initialising the application.** Run it at module level, not in a component.
12. **Hand-rolling a store subscription.** Use `useSyncExternalStore`.

Two consequences worth remembering. Setting state in an effect always costs an extra render
pass. And a derived effect chain makes the order of updates depend on render timing, which
is exactly the kind of bug that does not reproduce.

## Deriving instead of mirroring

The most common mistake in a data-heavy view is copying server data into local state so it
can be filtered or sorted. Derive it during render instead.

```tsx
// Wrong: two sources of truth, and an effect to keep them in sync.
const [visible, setVisible] = useState([])
useEffect(() => { setVisible(violations.filter(v => v.severity === filter)) }, [violations, filter])

// Right: one source of truth.
const visible = violations.filter(v => v.severity === filter)
```

If the derivation is genuinely expensive, the React Compiler will memoise it. Reach for
`useMemo` only when you have measured a problem and want explicit control.

## React 19 notes

**`use`** reads a promise or a context. The promise must come from a cache that survives
re-renders. Creating a promise during render and passing it to `use` produces a new promise
every render and will not work.

**Actions** cover the write paths in this application. `useActionState` gives the pending
flag, the error and the result in one place. `useOptimistic` shows the intended result
immediately and reverts on its own when the action fails, which is the behaviour to want
when the backend refuses a write that would have crossed a permission boundary.

**`useFormStatus`** reads the enclosing form's pending state without prop drilling, which is
what a shared button component in a design system needs.
