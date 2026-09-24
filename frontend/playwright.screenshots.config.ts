// `npm run screenshots`: every route at desktop and phone widths, for the visual review of
// spec 003 (AC 11, AC 12). A separate config so the gate's `playwright test` never runs it;
// it reuses the default config's two servers (the backend on its fixture, `vite preview`).
import { defineConfig } from '@playwright/test'

import base from './playwright.config'

export default defineConfig({
  ...base,
  testDir: './screenshots',
  outputDir: './screenshots/results',
  reporter: 'list',
})
