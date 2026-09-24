// Every route has zero serious or critical axe violations. Spec 002, AC 11 and NFR-02.
import AxeBuilder from '@axe-core/playwright'
import { expect, test } from '@playwright/test'

const WCAG_22_AA = ['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa', 'wcag22aa']

const ROUTES = [
  { path: '/scenes', ready: 'Escenas' },
  { path: '/scenes/002', ready: 'Escena 002' },
  { path: '/graph3d', ready: 'Grafo 3D' },
  { path: '/no-existe', ready: 'Página no encontrada' },
]

for (const { path, ready } of ROUTES) {
  // spec 002 / AC 11
  test(`no serious or critical axe violations on ${path}`, async ({ page }) => {
    await page.goto(path)
    await expect(page.getByRole('heading', { level: 1, name: ready })).toBeVisible()

    const { violations } = await new AxeBuilder({ page }).withTags(WCAG_22_AA).analyze()
    const blocking = violations
      .filter((violation) => violation.impact === 'serious' || violation.impact === 'critical')
      .map((violation) => `${violation.id}: ${violation.help} (${String(violation.nodes.length)} nodes)`)
    expect(blocking).toEqual([])
  })
}

// spec 003 / AC 2: the table of contents with the book header loaded.
test('no serious or critical axe violations on /scenes with the book header', async ({ page }) => {
  await page.goto('/scenes')
  await expect(page.getByText('Teodora Vance')).toBeVisible()
  await expect(page.getByRole('heading', { level: 2, name: 'ch01' })).toBeVisible()

  const { violations } = await new AxeBuilder({ page }).withTags(WCAG_22_AA).analyze()
  const blocking = violations
    .filter((violation) => violation.impact === 'serious' || violation.impact === 'critical')
    .map((violation) => `${violation.id}: ${violation.help} (${String(violation.nodes.length)} nodes)`)
  expect(blocking).toEqual([])
})
