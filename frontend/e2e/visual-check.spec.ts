// The visual check of one novel in the web reader (spec 014, AC 4-5; exam § 5a): the cover shows
// the title and the dedication, the index lists every chapter of the version, a chapter renders
// its text, and the character sheet links to at least one chapter. A page error or a failed
// step fails the check; the backend's `visual_check` validator returns that to the writer.
// Screenshots go to frontend/screenshots/visual-check/.
//
// Runs with e2e/visual-check.config.ts against a running reader; skipped without NOVEL_ID (so
// the default e2e config, which also looks in e2e/, never runs it by accident).
//
// Spec 018 (login): against a backend with AUTH_REQUIRED=1, set VISUAL_CHECK_EMAIL and
// VISUAL_CHECK_PASSWORD to a user who owns NOVEL_ID; the check logs in through the API and
// hands the token to the page. For a local visual check of CLI-generated novels (owned by
// `local`), start the backend with AUTH_REQUIRED=0 and leave both unset.
import { mkdirSync } from 'node:fs'
import { dirname, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'

import { expect, test } from '@playwright/test'

const NOVEL_ID = process.env['NOVEL_ID'] ?? ''
const EMAIL = process.env['VISUAL_CHECK_EMAIL'] ?? ''
const PASSWORD = process.env['VISUAL_CHECK_PASSWORD'] ?? ''
const TOKEN_KEY = 'msm.auth.token' // frontend/src/shared/api/auth-token.ts
const SHOTS = resolve(dirname(fileURLToPath(import.meta.url)), '../screenshots/visual-check')

interface NovelDetail {
  title: string | null
  dedication: string | null
  current_version: number | null
}

interface ChapterIndex {
  chapters: { n: number; title: string }[]
}

test.skip(NOVEL_ID === '', 'NOVEL_ID is not set')

test('the reader renders cover, index, a chapter and the character sheet', async ({ page, request }) => {
  mkdirSync(SHOTS, { recursive: true })
  const pageErrors: string[] = []
  page.on('pageerror', (error) => pageErrors.push(error.message))

  const headers: Record<string, string> = {}
  if (EMAIL !== '') {
    const login = await request.post('/api/auth/login', { data: { email: EMAIL, password: PASSWORD } })
    expect(login.ok(), 'the visual-check user can log in').toBe(true)
    const { access_token: token } = (await login.json()) as { access_token: string }
    headers['Authorization'] = `Bearer ${token}`
    await page.addInitScript(
      ([key, value]) => {
        window.localStorage.setItem(key, value)
      },
      [TOKEN_KEY, token] as const,
    )
  }

  const id = encodeURIComponent(NOVEL_ID)
  const novelResponse = await request.get(`/api/novels/${id}`, { headers })
  expect(novelResponse.ok(), 'the API answers for the novel').toBe(true)
  const novel = (await novelResponse.json()) as NovelDetail
  expect(novel.current_version, 'the novel has a published version').not.toBeNull()
  const version = String(novel.current_version)
  const index = (await (await request.get(`/api/novels/${id}/versions/${version}/chapters`, { headers })).json()) as ChapterIndex

  await test.step('cover: title and dedication', async () => {
    await page.goto(`/novelas/${id}`)
    const title = page.getByRole('heading', { level: 1 })
    await expect(title).toBeVisible()
    await expect(title).toHaveText(novel.title ?? 'Mi novela')
    const dedication = page.locator('.cover-dedication-text').first()
    await expect(dedication).toBeVisible()
    await expect(dedication).not.toBeEmpty()
    await page.screenshot({ path: `${SHOTS}/01-cover.png`, fullPage: true })
  })

  await test.step(`index: ${String(index.chapters.length)} chapter links`, async () => {
    await page.getByRole('navigation', { name: 'Lectura' }).getByRole('link', { name: 'Índice' }).click()
    const list = page.getByRole('list', { name: 'Capítulos' })
    await expect(list).toBeVisible()
    await expect(list.getByRole('link')).toHaveCount(index.chapters.length)
    await page.screenshot({ path: `${SHOTS}/02-index.png`, fullPage: true })
  })

  await test.step('chapter: text renders', async () => {
    await page.getByRole('list', { name: 'Capítulos' }).getByRole('link').first().click()
    const text = page.getByTestId('chapter-text')
    await expect(text).toBeVisible()
    expect((await text.innerText()).trim().length, 'the chapter has text').toBeGreaterThan(50)
    await page.screenshot({ path: `${SHOTS}/03-chapter.png`, fullPage: true })
  })

  await test.step('character sheet: at least one chapter link', async () => {
    await page.getByRole('navigation', { name: 'Lectura' }).getByRole('link', { name: 'Personajes y lugares' }).click()
    const sheets = page.getByTestId('bible-sheet')
    await expect(sheets.first()).toBeVisible()
    await expect(page.getByRole('region', { name: 'Personajes' }).getByRole('link', { name: /Capítulo \d+/ }).first()).toBeVisible()
    await page.screenshot({ path: `${SHOTS}/04-sheets.png`, fullPage: true })
  })

  expect(pageErrors, 'no uncaught errors in the page').toEqual([])
})
