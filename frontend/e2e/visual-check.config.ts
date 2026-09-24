// The visual check of the web reader (spec 014, exam § 5a). A config of its own: it starts no
// server, it opens a reader that is already running at BASE_URL (the Vite dev server or
// `vite preview`, whose `/api` proxy reaches the backend) and a novel given as NOVEL_ID.
//
//   NOVEL_ID=demo-faro BASE_URL=http://127.0.0.1:5173 npx playwright test --config e2e/visual-check.config.ts
//
// On this container the Playwright build of chromium differs from the one installed under
// /opt/pw-browsers, so the executable is named explicitly (override with CHROMIUM_PATH).
import { existsSync } from 'node:fs'

import { defineConfig, devices } from '@playwright/test'

const DEFAULT_CHROMIUM = '/opt/pw-browsers/chromium-1194/chrome-linux/chrome'
const chromium = process.env['CHROMIUM_PATH'] ?? (existsSync(DEFAULT_CHROMIUM) ? DEFAULT_CHROMIUM : undefined)

export default defineConfig({
  testDir: '.',
  testMatch: 'visual-check.spec.ts',
  outputDir: '../test-results/visual-check',
  retries: 0,
  reporter: 'list',
  timeout: 60_000,
  use: {
    baseURL: process.env['BASE_URL'] ?? 'http://127.0.0.1:5173',
    trace: 'retain-on-failure',
  },
  projects: [
    {
      name: 'chromium',
      use: {
        ...devices['Desktop Chrome'],
        ...(chromium === undefined ? {} : { launchOptions: { executablePath: chromium } }),
      },
    },
  ],
})
