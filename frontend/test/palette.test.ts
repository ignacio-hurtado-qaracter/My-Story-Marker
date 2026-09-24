// @vitest-environment node
// Every text and interactive colour pair of the design tokens meets WCAG 2.2 AA.
// Spec 003, FR-TOK-02 and AC 1.
import { readFileSync } from 'node:fs'

import { describe, expect, it } from 'vitest'

const tokensCss = readFileSync(new URL('../src/shared/ui/tokens.css', import.meta.url), 'utf8')

/** The `--name: #RRGGBB;` declarations of tokens.css. */
const tokens = new Map(
  [...tokensCss.matchAll(/--([a-z0-9-]+):\s*(#[0-9a-fA-F]{6})\s*;/g)].map((m) => [m[1] ?? '', (m[2] ?? '').toUpperCase()]),
)

function token(name: string): string {
  const value = tokens.get(name)
  if (value === undefined) throw new Error(`tokens.css declares no --${name}`)
  return value
}

/** WCAG 2.x relative luminance of a #RRGGBB colour. */
function luminance(hex: string): number {
  const channels = [1, 3, 5].map((i) => parseInt(hex.slice(i, i + 2), 16) / 255)
  const [r, g, b] = channels.map((c) => (c <= 0.03928 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4)) as [number, number, number]
  return 0.2126 * r + 0.7152 * g + 0.0722 * b
}

function contrast(a: string, b: string): number {
  const [hi, lo] = [luminance(a), luminance(b)].sort((x, y) => y - x) as [number, number]
  return (hi + 0.05) / (lo + 0.05)
}

/** Text pairs (4.5:1) of FR-TOK-02: foreground token on background token. */
const TEXT_PAIRS: [string, string][] = [
  ['ink', 'white'], ['ink', 'surface'], ['ink', 'brand-50'],
  ['ink-600', 'white'], ['ink-600', 'surface'],
  ['accent', 'white'], ['accent', 'surface'], ['accent', 'brand-50'], ['accent', 'brand-100'],
  ['white', 'accent'],
  ['muted', 'white'], ['muted', 'surface'], ['muted', 'brand-50'],
  ['pass', 'white'], ['pass', 'pass-tint'],
  ['fail', 'white'], ['fail', 'fail-tint'],
]

/** Non-text pairs (3:1): the focus outline and the active-pill fill against their surroundings. */
const UI_PAIRS: [string, string][] = [
  ['accent', 'white'], ['accent', 'surface'], ['accent', 'brand-50'],
  ['muted', 'white'],
]

describe('design token contrast', () => {
  // spec 003 / AC 1
  it.each(TEXT_PAIRS)('text --%s on --%s is at least 4.5:1', (fg, bg) => {
    expect(contrast(token(fg), token(bg))).toBeGreaterThanOrEqual(4.5)
  })

  // spec 003 / AC 1
  it.each(UI_PAIRS)('focus / state --%s against --%s is at least 3:1', (fg, bg) => {
    expect(contrast(token(fg), token(bg))).toBeGreaterThanOrEqual(3)
  })

  // spec 003 / AC 1: the check is live - main's original text orange would fail it.
  it("rejects main's original orange as a text colour", () => {
    expect(contrast('#E5661F', token('white'))).toBeLessThan(4.5)
    expect(contrast(token('white'), token('brand'))).toBeLessThan(4.5)
  })
})
