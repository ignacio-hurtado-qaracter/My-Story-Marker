// `npm run gate`: the frontend's full local gate, and exactly what CI runs. Spec 002, AC 1, 5, 14;
// plan decision P13.
//
// Every stage runs even when an earlier one fails, so one run shows everything that is wrong.
// The summary lists failures AND skips by name: a stage that cannot run here is reported as
// SKIPPED, never passed over in silence. The e2e stage may be skipped locally when the backend
// cannot be started; in CI (`CI` set) it is never skipped.
import { spawnSync } from 'node:child_process'
import { existsSync, readFileSync, readdirSync, statSync } from 'node:fs'
import { join, relative, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'

const frontendDir = fileURLToPath(new URL('..', import.meta.url))
const backendDir = join(frontendDir, '..', 'backend')
const inCI = process.env['CI'] !== undefined

/** Folders the suppression check scans (AC 1). */
const SCANNED = ['src', 'test', 'e2e', 'scripts']
const SOURCE = /\.(ts|tsx|mjs|js)$/
/** This file names the patterns it looks for, so it does not scan itself. */
const SELF = fileURLToPath(import.meta.url)

/**
 * AC 1 / FR-STATIC-03: no `any`, and no `@ts-ignore`, `@ts-expect-error` or `eslint-disable`
 * without a comment linking spec 002 on the same line.
 * @param {string} root
 * @returns {string[]} offending `file:line: text` entries
 */
export function findSuppressions(root) {
  /** @type {string[]} */
  const offences = []
  // A directive is a comment that starts with it; prose that mentions one is not.
  const suppression = /(\/\/|\/\*)\s*(@ts-ignore|@ts-expect-error|eslint-disable)/
  const explicitAny = /(:\s*any\b|\bas\s+any\b|<any>|\bany\[\])/
  /** @param {string} dir */
  const walk = (dir) => {
    for (const name of readdirSync(dir)) {
      const path = join(dir, name)
      if (statSync(path).isDirectory()) {
        walk(path)
      } else if (SOURCE.test(name) && !path.includes(join('shared', 'types')) && resolve(path) !== SELF) {
        readFileSync(path, 'utf8')
          .split('\n')
          .forEach((line, index) => {
            const where = `${relative(root, path).replaceAll('\\', '/')}:${String(index + 1)}`
            if (suppression.test(line) && !line.includes('spec 002')) offences.push(`${where}: ${line.trim()}`)
            if (explicitAny.test(line) && !line.trimStart().startsWith('//') && !line.trimStart().startsWith('*')) {
              offences.push(`${where}: ${line.trim()}`)
            }
          })
      }
    }
  }
  for (const folder of SCANNED) {
    const dir = join(root, folder)
    if (existsSync(dir)) walk(dir)
  }
  return offences
}

/**
 * AC 14 / FR-TOOL-01: every dependency version in package.json is exact.
 * @param {Record<string, unknown>} pkg
 * @returns {string[]} `name@range` entries that are not exact
 */
export function findRanges(pkg) {
  const exact = /^\d+\.\d+\.\d+$/
  /** @type {string[]} */
  const ranges = []
  const groups = [pkg['dependencies'], pkg['devDependencies'], pkg['optionalDependencies'], pkg['peerDependencies']]
  for (const deps of groups) {
    if (typeof deps !== 'object' || deps === null) continue
    for (const [name, version] of Object.entries(deps)) {
      // A prerelease suffix (`1.0.0-rc.1`) is still exact; a range never is.
      const core = typeof version === 'string' ? version.split('-')[0] ?? '' : ''
      if (!exact.test(core)) ranges.push(`${name}@${String(version)}`)
    }
  }
  return ranges
}

/** Can the e2e stage start the backend here? Mirrors e2e/backend.ts. */
function backendRunnable() {
  if (spawnSync('uv', ['--version'], { stdio: 'ignore' }).status === 0) return true
  const python =
    process.platform === 'win32' ? join(backendDir, '.venv', 'Scripts', 'python.exe') : join(backendDir, '.venv', 'bin', 'python')
  return existsSync(python)
}

/** @param {string} script */
function npm(script) {
  return () => {
    // One command string: with `shell`, Node would only concatenate an argument array (DEP0190).
    const result = spawnSync(`npm run -s ${script}`, { cwd: frontendDir, stdio: 'inherit', shell: true })
    return result.status === 0
  }
}

/** @type {{ name: string, run: () => boolean, skip?: () => string | null }[]} */
const STAGES = [
  { name: 'lint', run: npm('lint') },
  { name: 'typecheck', run: npm('typecheck') },
  { name: 'test', run: npm('test') },
  { name: 'check:api', run: npm('check:api') },
  { name: 'build', run: npm('build') },
  { name: 'check:bundle', run: npm('check:bundle') },
  {
    name: 'suppressions',
    run: () => {
      const offences = findSuppressions(frontendDir)
      for (const offence of offences) console.error(`  ${offence}`)
      return offences.length === 0
    },
  },
  {
    name: 'exact versions',
    run: () => {
      const ranges = findRanges(JSON.parse(readFileSync(join(frontendDir, 'package.json'), 'utf8')))
      for (const range of ranges) console.error(`  not exact: ${range}`)
      return ranges.length === 0
    },
  },
  {
    name: 'npm audit',
    run: () =>
      spawnSync('npm audit --omit=dev --audit-level=high', { cwd: frontendDir, stdio: 'inherit', shell: true }).status === 0,
  },
  {
    name: 'e2e',
    run: npm('e2e'),
    skip: () => (inCI || backendRunnable() ? null : 'the backend cannot be started here (no uv, no backend/.venv)'),
  },
]

function main() {
  /** @type {string[]} */
  const failures = []
  /** @type {string[]} */
  const skips = []
  for (const stage of STAGES) {
    const why = stage.skip?.() ?? null
    if (why !== null) {
      skips.push(`${stage.name} (${why})`)
      console.log(`\n=== ${stage.name} === SKIPPED: ${why}`)
      continue
    }
    console.log(`\n=== ${stage.name} ===`)
    if (!stage.run()) {
      failures.push(stage.name)
      console.log(`--- ${stage.name} FAILED`)
    }
  }
  console.log('\n=== gate summary ===')
  console.log(`passed:  ${String(STAGES.length - failures.length - skips.length)} of ${String(STAGES.length)}`)
  console.log(`failed:  ${failures.length === 0 ? 'none' : failures.join(', ')}`)
  console.log(`skipped: ${skips.length === 0 ? 'none' : skips.join(', ')}`)
  process.exitCode = failures.length === 0 ? 0 : 1
}

if (process.argv[1] === fileURLToPath(import.meta.url)) {
  main()
}
