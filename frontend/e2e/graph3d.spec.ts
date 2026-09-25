// three.js loads only on /graph3d, and mounts a canvas there. Spec 002, AC 13 and NFR-01.
import { expect, test, type Page } from '@playwright/test'

/** The lazily loaded scene chunk is named after its module, graph3d/PlanetScene.tsx. */
const SCENE_CHUNK = /\/assets\/PlanetScene-[^/]+\.js$/

function recordScripts(page: Page): string[] {
  const urls: string[] = []
  page.on('request', (request) => {
    if (request.resourceType() === 'script') urls.push(request.url())
  })
  return urls
}

// spec 002 / AC 13
test('the three.js chunk is requested on /graph3d and not on /arquitectura', async ({ page }) => {
  const scripts = recordScripts(page)

  await page.goto('/arquitectura')
  await expect(page.getByRole('heading', { level: 1, name: 'De la entrevista al libro' })).toBeVisible()
  expect(scripts.filter((url) => SCENE_CHUNK.test(url))).toEqual([])

  // Revised by spec 003 (revision 2): /graph3d is reached from the footer.
  await page.getByRole('contentinfo').getByRole('link', { name: 'Vista 3D' }).click()
  await expect(page.getByRole('heading', { level: 1, name: 'Grafo 3D' })).toBeVisible()
  await expect(page.locator('canvas')).toBeVisible()
  expect(scripts.filter((url) => SCENE_CHUNK.test(url))).toHaveLength(1)
})
