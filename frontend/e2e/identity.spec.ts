// The visual identity's observable promises, against the real app. Spec 003, AC 3, 4, 8, 9.
import { readFileSync, readdirSync } from 'node:fs'
import { join } from 'node:path'
import { fileURLToPath } from 'node:url'

import { expect, test, type Page } from '@playwright/test'

/** Each route, and the h1 that shows it has rendered. */
const PAGES = new Map([
  ['/scenes', 'Escenas'],
  ['/scenes/002', 'Escena 002'],
  ['/graph3d', 'Grafo 3D'],
  ['/no-existe', 'Página no encontrada'],
])
const ROUTES = [...PAGES.keys()]

async function open(page: Page, path: string): Promise<void> {
  await page.goto(path)
  await expect(page.getByRole('heading', { level: 1, name: PAGES.get(path) ?? '' })).toBeVisible()
}

// spec 003 / AC 3
test('every request stays on the app origin', async ({ page, baseURL }) => {
  const origin = new URL(baseURL ?? '').origin
  const foreign: string[] = []
  page.on('request', (request) => {
    const url = new URL(request.url())
    if (url.protocol.startsWith('http') && url.origin !== origin) foreign.push(request.url())
  })
  for (const path of ROUTES) {
    await open(page, path)
    await page.waitForLoadState('networkidle')
  }
  expect(foreign).toEqual([])
})

// spec 003 / AC 3
test('the built CSS uses only the self-hosted latin fonts', () => {
  const assets = fileURLToPath(new URL('../dist/assets/', import.meta.url))
  const css = readdirSync(assets)
    .filter((name) => name.endsWith('.css'))
    .map((name) => readFileSync(join(assets, name), 'utf8'))
    .join('\n')
  const fonts = [...css.matchAll(/url\(([^)]+\.woff2)\)/g)].map((m) => m[1] ?? '')
  expect(fonts.length).toBeGreaterThan(0)
  for (const url of fonts) {
    expect(url).not.toMatch(/^https?:/)
    expect(url).toMatch(/(inter-latin-(400|500|600|700)|jetbrains-mono-latin-400)-normal/)
  }
})

// spec 003 / AC 4
test('keyboard focus is visible, in the accent colour, and never under the sticky header', async ({ page }) => {
  await page.setViewportSize({ width: 1280, height: 520 })
  await open(page, '/scenes')
  // The title renders before the chapters; tab only once the chips exist.
  await expect(page.getByRole('link', { name: 'Escena 001' })).toBeVisible()

  const expected = ['My Story Marker', 'Escenas', 'Grafo 3D', 'Escena 001']
  for (const name of expected) {
    await page.keyboard.press('Tab')
    const focused = page.locator(':focus')
    await expect(focused).toHaveAccessibleName(name)
    const outline = await focused.evaluate((el) => {
      const style = getComputedStyle(el)
      return { style: style.outlineStyle, color: style.outlineColor, width: style.outlineWidth, offset: style.outlineOffset }
    })
    expect(outline.style).toBe('solid')
    expect(outline.color).toBe('rgb(174, 78, 20)')
    expect(parseFloat(outline.width)).toBeGreaterThanOrEqual(2)
    expect(parseFloat(outline.offset)).toBeGreaterThanOrEqual(2)
  }

  // Scroll away, then move focus back up to a chip: it must land below the header.
  await page.evaluate(() => {
    window.scrollTo(0, document.body.scrollHeight)
  })
  await page.getByRole('link', { name: 'Escena 004' }).focus()
  await page.keyboard.press('Shift+Tab')
  const headerBottom = await page.getByRole('banner').evaluate((el) => el.getBoundingClientRect().bottom)
  const focusedTop = await page.locator(':focus').evaluate((el) => el.getBoundingClientRect().top)
  expect(focusedTop).toBeGreaterThanOrEqual(headerBottom)
})

// spec 003 / AC 8
test('the health dot pulses, and stops under reduced motion', async ({ browser }) => {
  for (const reducedMotion of ['no-preference', 'reduce'] as const) {
    const context = await browser.newContext({ reducedMotion })
    const page = await context.newPage()
    await open(page, '/scenes')
    const badge = page.getByRole('status', { name: 'Estado del backend' })
    await expect(badge).toContainText('ok')
    const animation = await badge.evaluate((el) => getComputedStyle(el, '::before').animationName)
    if (reducedMotion === 'reduce') expect(animation).toBe('none')
    else expect(animation).not.toBe('none')
    await context.close()
  }
})

// spec 003 / AC 8
test('the planet moves while playing and stops when paused', async ({ page }) => {
  await open(page, '/graph3d')
  const canvas = page.locator('canvas')
  await expect(canvas).toBeVisible()
  const toggle = page.getByRole('button', { name: 'Pausar animación' })
  await expect(toggle).toHaveAttribute('aria-pressed', 'false')

  await page.waitForTimeout(800)
  const a = await canvas.screenshot()
  await page.waitForTimeout(500)
  const b = await canvas.screenshot()
  expect(a.equals(b)).toBe(false)

  await toggle.click()
  await expect(toggle).toHaveAttribute('aria-pressed', 'true')
  await page.waitForTimeout(300)
  const c = await canvas.screenshot()
  await page.waitForTimeout(500)
  const d = await canvas.screenshot()
  expect(c.equals(d)).toBe(true)
})

// spec 003 / AC 8
test('under reduced motion the planet starts paused', async ({ browser }) => {
  const context = await browser.newContext({ reducedMotion: 'reduce' })
  const page = await context.newPage()
  await open(page, '/graph3d')
  await expect(page.getByRole('button', { name: 'Pausar animación' })).toHaveAttribute('aria-pressed', 'true')
  await context.close()
})

async function overflows(page: Page): Promise<boolean> {
  return page.evaluate(() => document.documentElement.scrollWidth > window.innerWidth)
}

// spec 003 / AC 9
for (const viewport of [
  { width: 320, height: 640 },
  { width: 390, height: 844 },
]) {
  test(`no horizontal scrolling at ${String(viewport.width)} px`, async ({ page }) => {
    await page.setViewportSize(viewport)
    for (const path of ROUTES) {
      await open(page, path)
      expect({ path, overflows: await overflows(page) }).toEqual({ path, overflows: false })
    }
    // The check can fail: a planted 2 000 px element is detected.
    await page.evaluate(() => {
      const wide = document.createElement('div')
      wide.style.width = '2000px'
      wide.style.height = '1px'
      document.body.append(wide)
    })
    expect(await overflows(page)).toBe(true)
  })
}
