// Starts the real backend for the end-to-end run, on a throwaway copy of its fixture repository.
// Spec 002, NFR-05; plan decisions P8-P10. Playwright runs it as a `webServer` command
// (`node e2e/backend.ts`; Node 24 strips the types), and stops it when the run ends.
//
// - The fixture is copied to a temp directory, so no test can touch a working store (NFR-05).
// - Port 8765, so a developer's own backend on 8000 is never the one under test (P8).
// - EMBED_OFFLINE stays unset: with it set, a missing embedding model is a startup error, and
//   online nothing is loaded until a rebuild, which no test triggers (P9).
// - `uv run` when uv is on PATH (CI), else the backend's own virtualenv (P10).
import { spawn, spawnSync } from 'node:child_process'
import { cpSync, existsSync, mkdtempSync, rmSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import { fileURLToPath } from 'node:url'

export const BACKEND_PORT = 8765

const backendDir = fileURLToPath(new URL('../../backend/', import.meta.url))

function backendCommand(): { command: string; args: string[] } {
  const uvicorn = ['uvicorn', 'app.main:app', '--host', '127.0.0.1', '--port', String(BACKEND_PORT)]
  if (spawnSync('uv', ['--version'], { stdio: 'ignore' }).status === 0) {
    return { command: 'uv', args: ['run', '--no-sync', ...uvicorn] }
  }
  const venvPython =
    process.platform === 'win32' ? join(backendDir, '.venv', 'Scripts', 'python.exe') : join(backendDir, '.venv', 'bin', 'python')
  if (!existsSync(venvPython)) {
    throw new Error(`cannot start the backend: neither uv nor ${venvPython} is available`)
  }
  return { command: venvPython, args: ['-m', ...uvicorn] }
}

function main(): void {
  const workDir = mkdtempSync(join(tmpdir(), 'msm-e2e-'))
  const storyRoot = join(workDir, 'repo')
  cpSync(join(backendDir, 'tests', 'fixtures', 'repo'), storyRoot, { recursive: true })

  const { command, args } = backendCommand()
  const child = spawn(command, args, {
    cwd: backendDir,
    stdio: 'inherit',
    env: {
      ...process.env,
      STORY_ROOT: storyRoot,
      STORY_INDEX: join(workDir, 'index', 'index.sqlite'),
      PYTHONUTF8: '1',
    },
  })

  const stop = (): void => {
    child.kill()
  }
  process.on('SIGINT', stop)
  process.on('SIGTERM', stop)
  child.on('exit', (code) => {
    rmSync(workDir, { recursive: true, force: true })
    process.exit(code ?? 0)
  })
}

if (process.argv[1] === fileURLToPath(import.meta.url)) {
  main()
}
