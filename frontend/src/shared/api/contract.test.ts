// @vitest-environment node
// The contract gate of FR-API-03: `check:api` passes on the committed schema and fails after a
// one-field edit that was not regenerated. It runs the real CLI, as the gate and CI do.
// It runs in Node, so tsconfig.node.json type-checks it, not the browser project (spec 002, AC 4).
import { execFileSync, spawnSync } from 'node:child_process'
import { mkdtempSync, rmSync, writeFileSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import { fileURLToPath } from 'node:url'
import { afterAll, describe, expect, it } from 'vitest'

const frontendRoot = fileURLToPath(new URL('../../../', import.meta.url))
const checkApiScript = join(frontendRoot, 'scripts', 'check-api.mjs')
const timeout = 60_000

// The committed schema, not the working tree: a backend change in progress must not decide
// whether the committed client is fresh. Null when git (or the commit) is unavailable.
function committedSchema(): string | null {
  try {
    return execFileSync('git', ['show', 'HEAD:backend/openapi.json'], {
      cwd: frontendRoot,
      encoding: 'utf8',
      maxBuffer: 64 * 1024 * 1024,
      stdio: ['ignore', 'pipe', 'ignore'],
    })
  } catch {
    return null
  }
}

const schema = committedSchema()
const workDir = mkdtempSync(join(tmpdir(), 'check-api-'))

afterAll(() => {
  rmSync(workDir, { recursive: true, force: true })
})

function runCheckApi(schemaText: string, name: string) {
  const schemaPath = join(workDir, name)
  writeFileSync(schemaPath, schemaText, 'utf8')
  return spawnSync(process.execPath, [checkApiScript, '--schema', schemaPath], {
    cwd: frontendRoot,
    encoding: 'utf8',
  })
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value)
}

// One field: `HealthResponse.status` is renamed to `state`, everywhere the schema names it.
function renameHealthStatus(schemaText: string): string {
  const doc: unknown = JSON.parse(schemaText)
  const components = isRecord(doc) ? doc['components'] : undefined
  const schemas = isRecord(components) ? components['schemas'] : undefined
  const health = isRecord(schemas) ? schemas['HealthResponse'] : undefined
  const properties = isRecord(health) ? health['properties'] : undefined
  if (!isRecord(health) || !isRecord(properties) || !('status' in properties)) {
    throw new Error('the committed schema has no HealthResponse.status to mutate')
  }
  properties['state'] = properties['status']
  delete properties['status']
  const required = health['required']
  if (Array.isArray(required)) {
    health['required'] = required.map((field: unknown) => (field === 'status' ? 'state' : field))
  }
  return JSON.stringify(doc, null, 2)
}

describe.skipIf(schema === null)('check:api (skipped when `git show HEAD:backend/openapi.json` fails)', () => {
  const committed = schema ?? ''

  // spec 002 / AC 4
  it(
    'passes: the committed types are what the committed schema generates',
    () => {
      const result = runCheckApi(committed, 'openapi.json')
      expect(result.stderr).toBe('')
      expect(result.status).toBe(0)
      expect(result.stdout).toContain('check:api: OK')
    },
    timeout,
  )

  // spec 002 / AC 4
  it(
    'fails after a one-field edit to the schema that was not regenerated',
    () => {
      const result = runCheckApi(renameHealthStatus(committed), 'openapi.mutated.json')
      expect(result.status).toBe(1)
      expect(result.stderr).toContain('is stale')
    },
    timeout,
  )
})
