// Every route has zero serious or critical axe violations. Spec 002, AC 11 and NFR-02.
import AxeBuilder from '@axe-core/playwright'
import { expect, test } from '@playwright/test'

const WCAG_22_AA = ['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa', 'wcag22aa']

const ROUTES = [
  { path: '/', ready: null },
  { path: '/characters', ready: 'Personajes' },
  { path: '/characters/vance', ready: 'Teodora Vance' },
  { path: '/locations', ready: 'Lugares' },
  { path: '/locations/pump_vault', ready: 'Pump vault' },
  { path: '/graph3d', ready: 'Grafo 3D' },
  { path: '/no-existe', ready: 'Página no encontrada' },
]

for (const { path, ready } of ROUTES) {
  // spec 002 / AC 11
  test(`no serious or critical axe violations on ${path}`, async ({ page }) => {
    await page.goto(path)
    // Spec 003 revision 2: the cover's h1 is the personalised title, so only its presence is checked.
    const heading = ready === null ? page.getByRole('heading', { level: 1 }) : page.getByRole('heading', { level: 1, name: ready })
    await expect(heading).toBeVisible()

    const { violations } = await new AxeBuilder({ page }).withTags(WCAG_22_AA).analyze()
    const blocking = violations
      .filter((violation) => violation.impact === 'serious' || violation.impact === 'critical')
      .map((violation) => `${violation.id}: ${violation.help} (${String(violation.nodes.length)} nodes)`)
    expect(blocking).toEqual([])
  })
}

// spec 003 / AC 2: the cover with its premise and the chapter reader with its prose loaded.
test('no serious or critical axe violations on the loaded cover', async ({ page }) => {
  await page.goto('/')
  await expect(page.getByText('Teodora Vance, the last soak-certified diver')).toBeVisible()

  const { violations } = await new AxeBuilder({ page }).withTags(WCAG_22_AA).analyze()
  const blocking = violations
    .filter((violation) => violation.impact === 'serious' || violation.impact === 'critical')
    .map((violation) => `${violation.id}: ${violation.help} (${String(violation.nodes.length)} nodes)`)
  expect(blocking).toEqual([])
})
