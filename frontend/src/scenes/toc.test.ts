// The ordering functions of FR-SCN-01/03/04: examples, then fast-check properties (plan P11).
import fc from 'fast-check'
import { describe, expect, it } from 'vitest'

import type { Schemas } from '../shared/api'
import { buildToc, flatten, neighbours } from './toc'

type Chapter = Schemas['Chapter']

function chapter(id: string, scenes: string[]): Chapter {
  return {
    id,
    function: `función de ${id}`,
    arc: 'ar_test',
    budget: 1000,
    target_tension_in: 1,
    target_tension_out: 2,
    scenes,
  }
}

describe('buildToc', () => {
  // spec 002 / AC 8
  it('keeps chapter order and each chapter scene order, whatever order GET /scenes gives', () => {
    const toc = buildToc([chapter('ch01', ['003', '001']), chapter('ch02', ['002'])], ['002', '001', '003'])
    expect(toc).toEqual({
      chapters: [
        { id: 'ch01', function: 'función de ch01', scenes: ['003', '001'] },
        { id: 'ch02', function: 'función de ch02', scenes: ['002'] },
      ],
      unassigned: [],
    })
  })

  // spec 002 / AC 8
  it('puts scenes no chapter lists last, sorted by id', () => {
    const toc = buildToc([chapter('ch01', ['002'])], ['009', '002', '004'])
    expect(toc.unassigned).toEqual(['004', '009'])
    expect(flatten(toc)).toEqual(['002', '004', '009'])
  })

  it('keeps a scene a chapter lists but GET /scenes omits, and never duplicates one', () => {
    const toc = buildToc([chapter('ch01', ['001', '005', '001']), chapter('ch02', ['005', '002'])], ['001', '002'])
    expect(toc.chapters.map((c) => c.scenes)).toEqual([['001', '005'], ['002']])
    expect(flatten(toc)).toEqual(['001', '005', '002'])
  })

  it('treats a chapter without a scenes list as empty', () => {
    const bare: Chapter = {
      id: 'ch01',
      function: 'función de ch01',
      arc: 'ar_test',
      budget: 1000,
      target_tension_in: 1,
      target_tension_out: 2,
    }
    expect(buildToc([bare], ['001'])).toEqual({
      chapters: [{ id: 'ch01', function: 'función de ch01', scenes: [] }],
      unassigned: ['001'],
    })
  })

  it('is empty for no chapters and no scenes', () => {
    expect(buildToc([], [])).toEqual({ chapters: [], unassigned: [] })
  })
})

describe('neighbours', () => {
  const toc = buildToc([chapter('ch01', ['001', '002']), chapter('ch02', ['003'])], ['004', '003', '002', '001'])

  // spec 002 / AC 8
  it('crosses a chapter boundary and runs into the unassigned tail', () => {
    expect(neighbours(toc, '001')).toEqual({ next: '002' })
    expect(neighbours(toc, '002')).toEqual({ previous: '001', next: '003' })
    expect(neighbours(toc, '003')).toEqual({ previous: '002', next: '004' })
    expect(neighbours(toc, '004')).toEqual({ previous: '003' })
  })

  it('is empty for a scene the order does not contain', () => {
    expect(neighbours(toc, '999')).toEqual({})
  })
})

// Small id space, so chapters and GET /scenes overlap, repeat and disagree often.
const sceneId = fc.integer({ min: 1, max: 30 }).map((n) => String(n).padStart(3, '0'))
const chapters = fc
  .array(fc.array(sceneId, { maxLength: 6 }), { maxLength: 5 })
  .map((lists) => lists.map((scenes, index) => chapter(`ch${String(index + 1).padStart(2, '0')}`, scenes)))
const sceneIds = fc.array(sceneId, { maxLength: 20 })

describe('buildToc properties', () => {
  // spec 002 / AC 8
  it('lists every scene exactly once', () => {
    fc.assert(
      fc.property(chapters, sceneIds, (chs, ids) => {
        const order = flatten(buildToc(chs, ids))
        const expected = new Set([...chs.flatMap((c) => c.scenes ?? []), ...ids])
        expect(new Set(order)).toEqual(expected)
        expect(order).toHaveLength(expected.size)
      }),
    )
  })

  // spec 002 / AC 8
  it('keeps chapter order and each chapter scene order (first occurrence wins)', () => {
    fc.assert(
      fc.property(chapters, sceneIds, (chs, ids) => {
        const toc = buildToc(chs, ids)
        expect(toc.chapters.map((c) => c.id)).toEqual(chs.map((c) => c.id))
        const firstOccurrences = [...new Set(chs.flatMap((c) => c.scenes ?? []))]
        expect(toc.chapters.flatMap((c) => c.scenes)).toEqual(firstOccurrences)
      }),
    )
  })

  // spec 002 / AC 8
  it('puts the unassigned scenes last, and only scenes no chapter lists', () => {
    fc.assert(
      fc.property(chapters, sceneIds, (chs, ids) => {
        const toc = buildToc(chs, ids)
        const listed = new Set(chs.flatMap((c) => c.scenes ?? []))
        const order = flatten(toc)
        expect(order.slice(order.length - toc.unassigned.length)).toEqual(toc.unassigned)
        expect(toc.unassigned.every((id) => !listed.has(id))).toBe(true)
        expect(ids.filter((id) => !listed.has(id)).every((id) => toc.unassigned.includes(id))).toBe(true)
      }),
    )
  })
})

describe('neighbours properties', () => {
  // spec 002 / AC 8: across chapter boundaries and into the unassigned tail, since the order
  // tested is the whole flattened order.
  it('previous and next are inverse neighbours along the reading order', () => {
    fc.assert(
      fc.property(chapters, sceneIds, (chs, ids) => {
        const toc = buildToc(chs, ids)
        const order = flatten(toc)
        order.forEach((id, index) => {
          const { previous, next } = neighbours(toc, id)
          expect(previous).toBe(order[index - 1])
          expect(next).toBe(order[index + 1])
          if (next !== undefined) {
            expect(neighbours(toc, next).previous).toBe(id)
          }
          if (previous !== undefined) {
            expect(neighbours(toc, previous).next).toBe(id)
          }
        })
      }),
    )
  })
})
