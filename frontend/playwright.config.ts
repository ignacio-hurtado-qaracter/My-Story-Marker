// End-to-end runs against the real backend. Spec 002, AC 6, 10, 11, 13; plan step 8.
//
// Two servers: the backend on a temp copy of its fixture (e2e/backend.ts), and the production
// build served by `vite preview`, whose `/api` proxy points at that backend. A production build,
// not the dev server, so AC 13 sees real chunks.
import { defineConfig, devices } from '@playwright/test'

import { BACKEND_PORT } from './e2e/backend'

const FRONTEND_PORT = 4174

export default defineConfig({
  testDir: './e2e',
  fullyParallel: true,
  forbidOnly: process.env['CI'] !== undefined,
  retries: 0,
  reporter: process.env['CI'] === undefined ? 'list' : [['list'], ['html', { open: 'never' }]],
  use: {
    baseURL: `http://127.0.0.1:${String(FRONTEND_PORT)}`,
    trace: 'retain-on-failure',
  },
  projects: [{ name: 'chromium', use: { ...devices['Desktop Chrome'] } }],
  webServer: [
    {
      command: 'node e2e/backend.ts',
      url: `http://127.0.0.1:${String(BACKEND_PORT)}/health`,
      timeout: 120_000,
      reuseExistingServer: false,
      stdout: 'pipe',
    },
    {
      command: `npm run build && npx vite preview --host 127.0.0.1 --port ${String(FRONTEND_PORT)} --strictPort`,
      url: `http://127.0.0.1:${String(FRONTEND_PORT)}`,
      timeout: 180_000,
      reuseExistingServer: false,
      env: { VITE_BACKEND_URL: `http://127.0.0.1:${String(BACKEND_PORT)}` },
    },
  ],
})
