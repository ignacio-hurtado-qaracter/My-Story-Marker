// ESLint for frontend/. Spec 002, FR-STATIC-01/02; plan decision P5.
//
// The boundary rules are docs/architecture.md rules 2, 3, 5, 7 and 8 for the frontend:
//   (a) a feature imports another feature only through its index.ts      (rule 2)
//   (b) shared/ imports no feature and not app/                           (rule 3)
//   (c) no feature imports app/                                           (rule 8)
//   (d) no import cycles                                                  (rule 5)
//   (e) only shared/api/ may use openapi-fetch, fetch or XMLHttpRequest   (rule 7)
//   (f) only graph3d/ may import three or @react-three/*                  (FR-3D-02)
//   (g) app/ imports a feature only through its index.ts                  (FR-SHELL-02)
// Each one has a planted fixture under lint-fixtures/, exercised by test/lint.test.ts (AC 3).
import js from '@eslint/js'
import boundaries from 'eslint-plugin-boundaries'
import { createTypeScriptImportResolver } from 'eslint-import-resolver-typescript'
import importX from 'eslint-plugin-import-x'
import jsxA11y from 'eslint-plugin-jsx-a11y'
import reactHooks from 'eslint-plugin-react-hooks'
import security from 'eslint-plugin-security'
import globals from 'globals'
import tseslint from 'typescript-eslint'

const THREE_MODULES = ['three', 'three/*', '@react-three/*']
const TSCONFIG_APP = `${import.meta.dirname}/tsconfig.app.json`

/** Restricted packages, per folder: (e) and (f). */
const restrictedImports = (allowOpenapiFetch, allowThree) => [
  'error',
  {
    patterns: [
      ...(allowOpenapiFetch
        ? []
        : [{ group: ['openapi-fetch'], message: 'Only src/shared/api/ may use openapi-fetch (architecture rule 7).' }]),
      ...(allowThree
        ? []
        : [{ group: THREE_MODULES, message: 'Only src/graph3d/ may import three.js (spec 002, FR-3D-02).' }]),
    ],
  },
]

const restrictedGlobals = [
  'error',
  { name: 'fetch', message: 'Only src/shared/api/ may issue requests (architecture rule 7).' },
  { name: 'XMLHttpRequest', message: 'Only src/shared/api/ may issue requests (architecture rule 7).' },
]

export default tseslint.config(
  { ignores: ['dist/', 'node_modules/', 'lint-fixtures/', 'playwright-report/', 'test-results/', 'src/shared/types/'] },

  js.configs.recommended,

  // TypeScript sources: strict, type-aware.
  {
    files: ['**/*.{ts,tsx}'],
    extends: [...tseslint.configs.strictTypeChecked],
    languageOptions: {
      parserOptions: { projectService: true, tsconfigRootDir: import.meta.dirname },
    },
  },

  // Plain JavaScript (this file, scripts/): Node globals, no type-aware rules.
  {
    files: ['**/*.{js,mjs}'],
    extends: [tseslint.configs.disableTypeChecked],
    languageOptions: { globals: globals.node },
  },

  // Browser code.
  {
    files: ['src/**/*.{ts,tsx}', 'test/**/*.{ts,tsx}'],
    extends: [reactHooks.configs.flat['recommended-latest'], jsxA11y.flatConfigs.recommended],
    languageOptions: { globals: globals.browser },
  },

  security.configs.recommended,

  // Build tooling and tests read and write paths they compute themselves (the schema, the
  // generated types, temp copies, fixtures); none comes from a request. The rule stays on in
  // the application code.
  {
    files: ['scripts/**', 'test/**', 'e2e/**', '**/*.test.{ts,tsx}', '*.config.{js,ts}'],
    rules: { 'security/detect-non-literal-fs-filename': 'off' },
  },

  // Architecture boundaries (a)-(d), (g).
  {
    files: ['src/**/*.{ts,tsx}'],
    plugins: { boundaries, 'import-x': importX },
    settings: {
      // Both plugins resolve TypeScript imports through the app project. test/lint.test.ts
      // overrides these two settings to point at the fixtures' own tsconfig.
      ...importX.flatConfigs.typescript.settings,
      'import-x/resolver-next': [createTypeScriptImportResolver({ project: TSCONFIG_APP })],
      'import/resolver': { typescript: { project: TSCONFIG_APP } },
      'boundaries/elements': [
        { type: 'app', pattern: 'src/app' },
        { type: 'shared', pattern: 'src/shared/*', capture: ['segment'] },
        { type: 'feature', pattern: 'src/*', capture: ['feature'] },
      ],
    },
    rules: {
      'boundaries/dependencies': [
        'error',
        {
          default: 'allow',
          policies: [
            // (b) shared/ imports no feature and not app/.
            {
              from: { element: { type: 'shared' } },
              disallow: { to: { element: { types: { anyOf: ['app', 'feature'] } } } },
              message: 'shared/ must not import app/ or a feature (architecture rule 3).',
            },
            // (c) no feature imports app/.
            {
              from: { element: { type: 'feature' } },
              disallow: { to: { element: { type: 'app' } } },
              message: 'A feature must not import app/ (architecture rule 8).',
            },
            // (a) and (g): from outside a feature, only its index.ts. Imports inside one
            // feature are internal dependencies and are not matched.
            {
              disallow: { to: { element: { type: 'feature', fileInternalPath: '!index.ts' } } },
              message: 'Import a feature only through its index.ts (architecture rule 2; spec 002, FR-SHELL-02).',
            },
          ],
        },
      ],
      // (d) no cycles, between features or within one.
      'import-x/no-cycle': ['error', { ignoreExternal: true }],
    },
  },

  // (e) and (f): restricted packages and globals, re-allowed where the spec permits.
  {
    files: ['src/**/*.{ts,tsx}'],
    rules: {
      'no-restricted-imports': restrictedImports(false, false),
      'no-restricted-globals': restrictedGlobals,
    },
  },
  {
    files: ['src/shared/api/**/*.{ts,tsx}'],
    rules: {
      'no-restricted-imports': restrictedImports(true, false),
      'no-restricted-globals': 'off',
    },
  },
  {
    files: ['src/graph3d/**/*.{ts,tsx}'],
    rules: { 'no-restricted-imports': restrictedImports(false, true) },
  },
)
