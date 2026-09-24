// A chapter's display title and summary, parsed from its `function`. Spec 003, FR-INDEX-01,
// FR-READ-01, decision R2-4; plan 003 Q13.
//
// The backend has no chapter-title field. The story bible writes one as a quoted phrase that
// opens `Chapter.function` ('"The Sealed Half": every lawful way into the vault…'), so the
// title is that phrase and the summary is what follows it. A function that does not open with
// a quoted phrase has no title: the caller shows "Capítulo N".

/** A straight "…" or curly “…” pair at the very start, after optional whitespace. */
const OPENING_QUOTE = /^\s*(?:"([^"]*)"|“([^”]*)”)/

/** What separates the title from the rest: whitespace and a colon, dash, stop or comma. */
const SEPARATOR = /^[\s:;,.—–-]+/

/** The quoted phrase that opens `fn`, trimmed; `null` when there is none or it is blank. */
export function chapterTitle(fn: string): string | null {
  const match = OPENING_QUOTE.exec(fn)
  if (match === null) {
    return null
  }
  const title = (match[1] ?? match[2] ?? '').trim()
  return title === '' ? null : title
}

/**
 * The rest of `fn` once its title is taken off, starting with a capital; the whole of `fn`,
 * trimmed, when it has no title. May be empty.
 */
export function chapterSummary(fn: string): string {
  const match = OPENING_QUOTE.exec(fn)
  if (match === null || chapterTitle(fn) === null) {
    return fn.trim()
  }
  const rest = fn.slice(match[0].length).replace(SEPARATOR, '').trim()
  return rest.charAt(0).toLocaleUpperCase('es') + rest.slice(1)
}

/** The title a page shows for the chapter at 1-based position `number`. */
export function displayTitle(fn: string, number: number): string {
  return chapterTitle(fn) ?? `Capítulo ${String(number)}`
}
