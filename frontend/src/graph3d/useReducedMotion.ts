// Whether the user asked the system for less motion. Spec 003, FR-3D-04: the planet starts
// paused under `prefers-reduced-motion: reduce`. Local to graph3d/, its only user.
//
// A useSyncExternalStore subscription to the media query's `change` events, so the value is
// read during render without an effect. Environments without matchMedia (jsdom) report false.
import { useSyncExternalStore } from 'react'

const QUERY = '(prefers-reduced-motion: reduce)'

function reducedMotionQuery(): MediaQueryList | null {
  return typeof window.matchMedia === 'function' ? window.matchMedia(QUERY) : null
}

function subscribe(onChange: () => void): () => void {
  const query = reducedMotionQuery()
  if (query === null) return () => {}
  query.addEventListener('change', onChange)
  return () => {
    query.removeEventListener('change', onChange)
  }
}

function getSnapshot(): boolean {
  return reducedMotionQuery()?.matches ?? false
}

/** Nothing is rendered on a server; the value only matters in the browser. */
function getServerSnapshot(): boolean {
  return false
}

export function useReducedMotion(): boolean {
  return useSyncExternalStore(subscribe, getSnapshot, getServerSnapshot)
}
