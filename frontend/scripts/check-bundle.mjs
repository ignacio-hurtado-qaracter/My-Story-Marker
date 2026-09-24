// `npm run check:bundle`: the initial JavaScript of /scenes holds no three.js and stays within
// budget. Spec 002, AC 12 and NFR-01; plan decision P12.
//
// The Vite manifest lists chunks but not the modules inside them, so three.js inlined into the
// entry chunk would pass unseen. `npm run build` therefore writes dist/bundle-report.json (the
// bundle-report plugin in vite.config.ts), which carries every chunk's module ids.
import { readFileSync } from 'node:fs'
import { join } from 'node:path'
import { fileURLToPath } from 'node:url'
import { gzipSync } from 'node:zlib'

/** NFR-01: 250 KB gzipped, for everything the entry chunk loads statically. */
export const BUDGET_BYTES = 250 * 1024

/** A module id that belongs to three.js or react-three-fiber. */
const THREE_MODULE = /[\\/]node_modules[\\/](three|@react-three)[\\/]/

/**
 * @typedef {object} ChunkReport
 * @property {string} fileName
 * @property {boolean} isEntry
 * @property {string[]} imports          static imports, by file name
 * @property {string[]} dynamicImports   lazy imports, by file name
 * @property {string[]} modules          module ids bundled into the chunk
 */

/**
 * @typedef {object} BundleCheck
 * @property {boolean} ok
 * @property {string[]} problems
 * @property {string[]} initialFiles     the entry chunk and its static-import closure
 * @property {number} gzipBytes
 */

/**
 * Check a bundle report: walk the entry chunk's static imports, fail on any three.js module in
 * that closure, and sum its gzipped size.
 * @param {ChunkReport[]} report
 * @param {(fileName: string) => number} gzipSizeOf
 * @param {number} [budgetBytes]
 * @returns {BundleCheck}
 */
export function checkBundle(report, gzipSizeOf, budgetBytes = BUDGET_BYTES) {
  const byFile = new Map(report.map((chunk) => [chunk.fileName, chunk]))
  const entries = report.filter((chunk) => chunk.isEntry)
  /** @type {string[]} */
  const problems = []
  if (entries.length !== 1) {
    problems.push(`expected exactly one entry chunk, found ${String(entries.length)}`)
  }

  /** @type {Set<string>} */
  const initial = new Set()
  const pending = entries.map((chunk) => chunk.fileName)
  while (pending.length > 0) {
    const fileName = pending.pop()
    if (fileName === undefined || initial.has(fileName)) continue
    initial.add(fileName)
    const chunk = byFile.get(fileName)
    if (chunk === undefined) {
      problems.push(`${fileName} is imported but missing from the report`)
      continue
    }
    pending.push(...chunk.imports)
  }

  for (const fileName of initial) {
    for (const moduleId of byFile.get(fileName)?.modules ?? []) {
      if (THREE_MODULE.test(moduleId)) {
        problems.push(`three.js module in the initial bundle (${fileName}): ${moduleId}`)
      }
    }
  }

  let gzipBytes = 0
  for (const fileName of initial) gzipBytes += gzipSizeOf(fileName)
  if (gzipBytes > budgetBytes) {
    problems.push(`initial JavaScript is ${String(gzipBytes)} B gzipped, over the ${String(budgetBytes)} B budget`)
  }

  return { ok: problems.length === 0, problems, initialFiles: [...initial].sort(), gzipBytes }
}

/** @param {string} distDir */
function gzipSizeIn(distDir) {
  return (/** @type {string} */ fileName) => gzipSync(readFileSync(join(distDir, fileName))).length
}

if (process.argv[1] === fileURLToPath(import.meta.url)) {
  const distDir = fileURLToPath(new URL('../dist/', import.meta.url))
  /** @type {ChunkReport[]} */
  const report = JSON.parse(readFileSync(join(distDir, 'bundle-report.json'), 'utf8'))
  const result = checkBundle(report, gzipSizeIn(distDir))
  const kb = (result.gzipBytes / 1024).toFixed(1)
  if (result.ok) {
    console.log(`check:bundle: OK, no three.js in the initial bundle, ${kb} KB gzipped (${result.initialFiles.join(', ')})`)
  } else {
    for (const problem of result.problems) console.error(`check:bundle: ${problem}`)
    process.exitCode = 1
  }
}
