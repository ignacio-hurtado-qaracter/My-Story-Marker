// The reader walk against the real backend on its fixture. Spec 002, AC 10.
//
// The fixture (backend/tests/fixtures/repo/) has two chapters, ch01 (001-003) and ch02
// (004-006); drafts exist only for 002 and 003, so 001 shows the no-draft empty state.
import { expect, test } from '@playwright/test'

// spec 002 / AC 10
test('table of contents, a scene with prose, next, and a scene without a draft', async ({ page }) => {
  await page.goto('/scenes')
  // Revised by spec 003 (revision 2): the index is titled "Índice" and chapters show their titles.
  await expect(page.getByRole('heading', { level: 1, name: 'Índice' })).toBeVisible()
  await expect(page.getByRole('heading', { level: 2, name: 'The Sealed Half' })).toBeVisible()
  await expect(page.getByRole('heading', { level: 2, name: 'The Calving Window' })).toBeVisible()

  await page.getByRole('link', { name: 'Escena 002' }).click()
  await expect(page).toHaveURL(/\/scenes\/002$/)
  await expect(page.getByRole('heading', { level: 1, name: 'Escena 002' })).toBeVisible()
  await expect(page.getByText('The co-op booked it as an indemnity dive')).toBeVisible()

  await page.getByRole('navigation', { name: 'Escenas vecinas' }).getByRole('link', { name: 'Siguiente: 003' }).click()
  await expect(page).toHaveURL(/\/scenes\/003$/)
  await expect(page.getByText('At four metres the lamp stopped being a lamp')).toBeVisible()

  await page.goto('/scenes/001')
  await expect(page.getByRole('heading', { level: 1, name: 'Escena 001' })).toBeVisible()
  await expect(page.getByText('Esta escena aún no tiene borrador')).toBeVisible()
})
