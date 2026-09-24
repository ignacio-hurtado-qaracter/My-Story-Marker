// @vitest-environment node
// The bundle check fails when it should. Spec 002, AC 12; plan decision P12.
import { describe, expect, it } from 'vitest'

import { BUDGET_BYTES, checkBundle } from '../scripts/check-bundle.mjs'

const THREE = '/repo/frontend/node_modules/three/build/three.module.js'
const FIBER = '/repo/frontend/node_modules/@react-three/fiber/dist/index.js'
const REACT = '/repo/frontend/node_modules/react/index.js'
const APP = '/repo/frontend/src/main.tsx'

const clean = [
  { fileName: 'assets/index.js', isEntry: true, imports: ['assets/vendor.js'], dynamicImports: ['assets/EmptyScene.js'], modules: [APP] },
  { fileName: 'assets/vendor.js', isEntry: false, imports: [], dynamicImports: [], modules: [REACT] },
  { fileName: 'assets/EmptyScene.js', isEntry: false, imports: [], dynamicImports: [], modules: [THREE, FIBER] },
]

const smallFiles = () => 1000

describe('checkBundle', () => {
  // spec 002 / AC 12
  it('passes when three.js is only in a lazily loaded chunk', () => {
    const result = checkBundle(clean, smallFiles)
    expect(result.problems).toEqual([])
    expect(result.initialFiles).toEqual(['assets/index.js', 'assets/vendor.js'])
    expect(result.gzipBytes).toBe(2000)
  })

  // spec 002 / AC 12: the planted report
  it('fails when a three.js module is inlined into the entry chunk', () => {
    const planted = clean.map((chunk) => (chunk.isEntry ? { ...chunk, modules: [APP, THREE] } : chunk))
    const result = checkBundle(planted, smallFiles)
    expect(result.ok).toBe(false)
    expect(result.problems.join('\n')).toContain('three.js module in the initial bundle')
  })

  // spec 002 / AC 12
  it('fails when a statically imported chunk carries react-three-fiber', () => {
    const planted = clean.map((chunk) => (chunk.fileName === 'assets/vendor.js' ? { ...chunk, modules: [REACT, FIBER] } : chunk))
    expect(checkBundle(planted, smallFiles).ok).toBe(false)
  })

  // spec 002 / AC 12
  it('fails over the 250 KB budget', () => {
    const result = checkBundle(clean, () => BUDGET_BYTES)
    expect(result.ok).toBe(false)
    expect(result.problems.join('\n')).toContain('over the')
  })
})
