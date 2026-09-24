// Display names the story bible does not store, derived from what it does. Spec 003, FR-BIBLE-02..04;
// spec decisions R2-4 and R2-5; plan decision Q13.
//
// The scenes feature parses chapter titles in its own module: two lines are not worth a shared
// module that would bind two features together (Q13).

/** A chapter function that opens with a quoted phrase: straight or curly double quotes. */
const OPENING_QUOTE = /^\s*["“]([^"“”]+)["”]/

/**
 * R2-4: the chapter's display title is the quoted phrase that opens `Chapter.function`
 * (`"The Sealed Half": every lawful way…` → `The Sealed Half`), or `null` when it has none.
 */
export function chapterDisplayTitle(chapterFunction: string): string | null {
  const title = OPENING_QUOTE.exec(chapterFunction)?.[1]?.trim()
  return title === undefined || title === '' ? null : title
}

/** What a chapter is called on screen: its display title, else "Capítulo N". */
export function chapterName(chapterNumber: number, title: string | null): string {
  return title ?? `Capítulo ${String(chapterNumber)}`
}

/** An identifier as words: `left_forearm` → `Left forearm`. */
export function humanizeId(id: string): string {
  const words = id
    .split(/[_-]+/)
    .filter((word) => word !== '')
    .join(' ')
  return words === '' ? id : words.charAt(0).toLocaleUpperCase('es') + words.slice(1)
}

/** R2-5: `Location` has no name field, so its name is its id as words (`pump_vault` → `Pump vault`). */
export function locationName(id: string): string {
  return humanizeId(id)
}

/** The first letters of the first and the last word: `Teodora Vance` → `TV`, `Quiej` → `Q`. */
export function initials(name: string): string {
  const words = name.trim().split(/\s+/).filter((word) => word !== '')
  const first = words[0]
  const last = words.length > 1 ? words[words.length - 1] : undefined
  const letters = [first, last].map((word) => (word === undefined ? '' : (Array.from(word)[0] ?? '')))
  const result = letters.join('').toLocaleUpperCase('es')
  return result === '' ? '?' : result
}

/** `12` → `12 capítulos`, `1` → `1 capítulo`. */
export function plural(count: number, one: string, many: string): string {
  return `${String(count)} ${count === 1 ? one : many}`
}
