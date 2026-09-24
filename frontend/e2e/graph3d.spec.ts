// three.js loads only on /graph3d, and mounts a canvas there. Spec 002, AC 13 and NFR-01.
import { expect, test, type Page } from '@playwright/test'

/** The lazily loaded scene chunk is named after its module, graph3d/EmptyScene.tsx. */
const SCENE_CHUNK = /\/assets\/EmptyScene-[^/]+\.js$/

function recordScripts(page: Page): string[] {
  const urls: string[] = []
  page.on('request', (request) => {
    if (request.resourceType() === 'script') urls.push(request.url())
  })
  return urls
}

// spec 002 / AC 13
test('the three.js chunk is requested on /graph3d and not on /scenes', async ({ page }) => {
  const scripts = recordScripts(page)

  await page.goto('/scenes')
  await expect(page.getByRole('heading', { level: 1, name: 'Escenas' })).toBeVisible()
  expect(scripts.filter((url) => SCENE_CHUNK.test(url))).toEqual([])

  await page.getByRole('link', { name: 'Grafo 3D' }).click()
  await expect(page.getByRole('heading', { level: 1, name: 'Grafo 3D' })).toBeVisible()
  await expect(page.locator('canvas')).toBeVisible()
  expect(scripts.filter((url) => SCENE_CHUNK.test(url))).toHaveLength(1)
})
