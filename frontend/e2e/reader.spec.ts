// The reader's walk against the real backend on its fixture. Spec 003, AC 18.
//
// Fixture (backend/tests/fixtures/repo/): chapters ch01 "The Sealed Half" (001-003) and ch02
// "The Calving Window" (004-006); drafts only for 002 and 003; cast vance (Teodora Vance), ilan,
// quiej; locations kestrel_deep (root) and pump_vault (its child).
import { expect, test } from '@playwright/test'

// spec 003 / AC 18
test('cover -> first chapter -> next chapter', async ({ page }) => {
  await page.goto('/')
  await expect(page.getByRole('heading', { level: 1 })).toBeVisible()
  await expect(page.getByText('Teodora Vance, the last soak-certified diver')).toBeVisible()

  await page.getByRole('link', { name: 'Empezar a leer' }).click()
  await expect(page).toHaveURL(/\/chapters\/ch01$/)
  await expect(page.getByRole('heading', { level: 1, name: 'The Sealed Half' })).toBeVisible()
  await expect(page.getByText('The co-op booked it as an indemnity dive')).toBeVisible()
  await expect(page.getByRole('navigation', { name: 'Índice de capítulos' })).toBeVisible()

  await page.getByRole('link', { name: /Capítulo siguiente/ }).click()
  await expect(page).toHaveURL(/\/chapters\/ch02$/)
  await expect(page.getByRole('heading', { level: 1, name: 'The Calving Window' })).toBeVisible()
})

// spec 003 / AC 18
test('a character sheet links to the chapters where she appears', async ({ page }) => {
  await page.goto('/')
  await page.getByRole('navigation', { name: 'Principal' }).getByRole('link', { name: 'Personajes' }).click()
  await expect(page.getByRole('heading', { level: 1, name: 'Personajes' })).toBeVisible()

  await page.getByRole('link', { name: 'Teodora Vance' }).first().click()
  await expect(page).toHaveURL(/\/characters\/vance$/)
  await expect(page.getByRole('heading', { level: 1, name: 'Teodora Vance' })).toBeVisible()

  const appearances = page.getByRole('region', { name: 'Aparece en' })
  await appearances.getByRole('link', { name: /The Sealed Half/ }).first().click()
  await expect(page).toHaveURL(/\/chapters\/ch01/)
  await expect(page.getByRole('heading', { level: 1, name: 'The Sealed Half' })).toBeVisible()
})

// spec 003 / AC 18
test('a location sheet shows its parent', async ({ page }) => {
  await page.goto('/locations')
  await expect(page.getByRole('heading', { level: 1, name: 'Lugares' })).toBeVisible()
  await page.getByRole('link', { name: 'Pump vault' }).first().click()
  await expect(page).toHaveURL(/\/locations\/pump_vault$/)
  await expect(page.getByRole('heading', { level: 1, name: 'Pump vault' })).toBeVisible()
  await expect(page.getByRole('link', { name: 'Kestrel deep' }).first()).toHaveAttribute('href', '/locations/kestrel_deep')
})
