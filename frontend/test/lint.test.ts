// @vitest-environment node
// The boundary rules of spec 002, FR-STATIC-02, each proven against a planted violation.
//
// lint-fixtures/ is a miniature src/ tree. Every file names what it must raise in its first
// line, `// expect: <rule-id>` or `// expect: none`. This test lints the tree with the
// project's own eslint.config.js, with type-aware rules off (plan P6) and the import resolvers
// pointed at the fixtures' tsconfig, and checks every file against its header.
import { readFileSync } from 'node:fs'
import { join, relative, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'

import { ESLint } from 'eslint'
import { createTypeScriptImportResolver } from 'eslint-import-resolver-typescript'
import tseslint from 'typescript-eslint'
import { beforeAll, describe, expect, it } from 'vitest'

const frontendRoot = fileURLToPath(new URL('..', import.meta.url))
const fixturesRoot = join(frontendRoot, 'lint-fixtures')
const fixturesProject = join(fixturesRoot, 'tsconfig.app.json')

/** The rule each boundary letter of FR-STATIC-02 is enforced by, and its planted file. */
const PLANTED = [
  { letter: 'a', file: 'src/beta/ImportsInternal.ts', rule: 'boundaries/dependencies' },
  { letter: 'b', file: 'src/shared/ui/ImportsFeature.ts', rule: 'boundaries/dependencies' },
  { letter: 'c', file: 'src/beta/ImportsApp.ts', rule: 'boundaries/dependencies' },
  { letter: 'd', file: 'src/alpha/cycleA.ts', rule: 'import-x/no-cycle' },
  { letter: 'e', file: 'src/beta/UsesFetch.ts', rule: 'no-restricted-globals' },
  { letter: 'e', file: 'src/beta/UsesOpenapiFetch.ts', rule: 'no-restricted-imports' },
  { letter: 'f', file: 'src/beta/UsesThree.ts', rule: 'no-restricted-imports' },
  { letter: 'g', file: 'src/app/AppReachesIn.ts', rule: 'boundaries/dependencies' },
] as const

/** Rule ids raised per fixture file, keyed by its path relative to lint-fixtures/. */
const raised = new Map<string, string[]>()

function expectedFor(file: string): string {
  const header = readFileSync(join(fixturesRoot, file), 'utf8').split('\n')[0] ?? ''
  const match = /^\/\/ expect: (\S+)/.exec(header)
  if (match?.[1] === undefined) {
    throw new Error(`${file} has no "// expect:" header`)
  }
  return match[1]
}

beforeAll(async () => {
  const eslint = new ESLint({
    cwd: fixturesRoot,
    overrideConfigFile: join(frontendRoot, 'eslint.config.js'),
    overrideConfig: [
      tseslint.configs.disableTypeChecked,
      {
        files: ['**/*.ts'],
        settings: {
          'import-x/resolver-next': [createTypeScriptImportResolver({ project: fixturesProject })],
          'import/resolver': { typescript: { project: fixturesProject } },
        },
      },
    ],
  })
  const results = await eslint.lintFiles(['src/**/*.ts'])
  for (const result of results) {
    const file = relative(fixturesRoot, result.filePath).replaceAll('\\', '/')
    raised.set(
      file,
      result.messages.map((message) => message.ruleId ?? `fatal: ${message.message}`),
    )
  }
}, 120_000)

describe('boundary rules (FR-STATIC-02)', () => {
  // spec 002 / AC 3
  it.each(PLANTED)('rule ($letter) fires on its planted fixture $file', ({ file, rule }) => {
    expect(expectedFor(file)).toBe(rule)
    expect(raised.get(file)).toEqual([rule])
  })

  // spec 002 / AC 3
  it('raises exactly what each fixture header says, and nothing on the accepted imports', () => {
    expect(raised.size).toBeGreaterThan(0)
    for (const [file, rules] of raised) {
      const expected = expectedFor(file)
      expect({ file, rules }).toEqual({ file, rules: expected === 'none' ? [] : [expected] })
    }
  })

  // spec 002 / AC 3
  it('the planted list covers every boundary letter (a)-(g)', () => {
    expect(new Set(PLANTED.map((p) => p.letter))).toEqual(new Set(['a', 'b', 'c', 'd', 'e', 'f', 'g']))
    expect(resolve(fixturesRoot)).toBe(fixturesRoot)
  })
})
