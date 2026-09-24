// Screenshots of every route for the visual review. Spec 003, AC 11. Output is git-ignored.
import { expect, test } from '@playwright/test'

const SHOTS = [
  { name: 'scenes', path: '/scenes', ready: 'Escenas', text: 'Teodora Vance' },
  { name: 'scene-002', path: '/scenes/002', ready: 'Escena 002', text: 'The co-op booked it' },
  { name: 'scene-001-no-draft', path: '/scenes/001', ready: 'Escena 001', text: 'Esta escena aún no tiene borrador' },
  { name: 'graph3d', path: '/graph3d', ready: 'Grafo 3D', text: null },
  { name: 'not-found', path: '/no-existe', ready: 'Página no encontrada', text: null },
] as const

const VIEWPORTS = [
  { label: 'desktop', width: 1280, height: 800 },
  { label: 'phone', width: 390, height: 844 },
] as const

for (const viewport of VIEWPORTS) {
  for (const shot of SHOTS) {
    // spec 003 / AC 11
    test(`${shot.name} at ${viewport.label}`, async ({ page }) => {
      await page.setViewportSize({ width: viewport.width, height: viewport.height })
      await page.goto(shot.path)
      await expect(page.getByRole('heading', { level: 1, name: shot.ready })).toBeVisible()
      if (shot.text !== null) await expect(page.getByText(shot.text).first()).toBeVisible()
      if (shot.name === 'graph3d') await page.waitForTimeout(1500)
      await page.screenshot({ path: `screenshots/out/${shot.name}-${viewport.label}.png`, fullPage: true })
    })
  }
}
