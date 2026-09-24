// `npm run check:api`: fails when the committed generated types are stale. Spec 002, FR-API-03.
// It regenerates in memory with the same `generate` as `gen:api` (P7) and compares.
import { readFile } from 'node:fs/promises'

import { generate, isMain, normalise, schemaPathFromArgs, TYPES_PATH } from './openapi.mjs'

/**
 * @typedef {{ ok: true } | { ok: false, message: string }} CheckResult
 */

/**
 * Compare a fresh generation from `schemaPath` with the file at `typesPath`.
 * @param {string} schemaPath
 * @param {string} [typesPath]
 * @returns {Promise<CheckResult>}
 */
export async function checkApi(schemaPath, typesPath = TYPES_PATH) {
  const expected = await generate(schemaPath)
  /** @type {string} */
  let committed
  try {
    committed = normalise(await readFile(typesPath, 'utf8'))
  } catch {
    return { ok: false, message: `check:api: ${typesPath} is missing. Run \`npm run gen:api\`.` }
  }
  if (committed === expected) {
    return { ok: true }
  }
  return {
    ok: false,
    message:
      `check:api: ${typesPath} is stale against ${schemaPath}.\n` +
      'Run `npm run gen:api` and commit the result as a `contract:` commit (spec 002, P14).',
  }
}

if (isMain(import.meta.url)) {
  const schemaPath = schemaPathFromArgs(process.argv.slice(2))
  const result = await checkApi(schemaPath)
  if (result.ok) {
    console.log('check:api: OK, the generated types match the schema')
  } else {
    console.error(result.message)
    process.exitCode = 1
  }
}
