// Chapter display titles parsed from `function`. Spec 003, FR-INDEX-01, R2-4, AC 14; plan Q13.
import fc from 'fast-check'
import { describe, expect, it } from 'vitest'

import { chapterSummary, chapterTitle, displayTitle } from './chapterTitle'

// The two chapters of backend/tests/fixtures/repo/structure/chapters.yaml, verbatim.
const CH01 =
  '"The Sealed Half": every lawful way into the vault is closed to Vance, and the reader learns through Ilan what the co-op takes from the people who go down for it.'
const CH02 =
  '"The Calving Window": the sealing order stops being paper and becomes a clock, and what Vance recovers from the vault she recovers out of her brother rather than out of the co-op.'

describe('chapterTitle', () => {
  // spec 003 / AC 14
  it('takes the quoted phrase that opens the fixture functions', () => {
    expect(chapterTitle(CH01)).toBe('The Sealed Half')
    expect(chapterTitle(CH02)).toBe('The Calving Window')
  })

  // spec 003 / AC 14
  it('accepts curly quotes and leading whitespace, and trims the phrase', () => {
    expect(chapterTitle('“La mitad sellada”: la bóveda se cierra.')).toBe('La mitad sellada')
    expect(chapterTitle('  \n"  Espacios  " — resto')).toBe('Espacios')
  })

  // spec 003 / AC 14
  it('returns null when the function does not open with a quoted phrase', () => {
    expect(chapterTitle('Función dramática de ch01')).toBeNull()
    expect(chapterTitle('Vance learns "the truth" too late.')).toBeNull()
    expect(chapterTitle('"Sin cerrar: falta la comilla')).toBeNull()
    expect(chapterTitle('"Mezcladas” no cuentan')).toBeNull()
    expect(chapterTitle('"": vacío')).toBeNull()
    expect(chapterTitle('"   ": en blanco')).toBeNull()
    expect(chapterTitle('')).toBeNull()
  })

  // spec 003 / AC 14
  it('finds any quote-free phrase that opens a function', () => {
    const phrase = fc.string().filter((s) => !/["“”]/.test(s) && s.trim() !== '')
    fc.assert(
      fc.property(phrase, fc.string(), (title, rest) => {
        expect(chapterTitle(`"${title}"${rest}`)).toBe(title.trim())
        expect(chapterTitle(`“${title}”${rest}`)).toBe(title.trim())
      }),
    )
  })
})

describe('chapterSummary', () => {
  // spec 003 / AC 14
  it('keeps what follows the title, without the separator, starting with a capital', () => {
    expect(chapterSummary(CH01)).toBe(
      'Every lawful way into the vault is closed to Vance, and the reader learns through Ilan what the co-op takes from the people who go down for it.',
    )
    expect(chapterSummary('“Título” — el resto.')).toBe('El resto.')
    expect(chapterSummary('"Solo el título"')).toBe('')
  })

  // spec 003 / AC 14
  it('is the whole function, trimmed, when there is no title', () => {
    expect(chapterSummary('  Función dramática de ch01  ')).toBe('Función dramática de ch01')
    expect(chapterSummary('""  sin título')).toBe('""  sin título')
  })
})

describe('displayTitle', () => {
  // spec 003 / AC 14
  it('falls back to "Capítulo N"', () => {
    expect(displayTitle(CH01, 1)).toBe('The Sealed Half')
    expect(displayTitle('Función dramática de ch03', 3)).toBe('Capítulo 3')
  })
})
