// The premise of the book, inside the table of contents' header card. Spec 003, FR-BOOK-01/02.
//
// Only the statement and the dramatic question are shown: the premise's `answer` is how the book
// resolves, a spoiler, and is never rendered. The premise is an extra: while it loads, a
// decorative line stands in for it (the table of contents' skeleton stays the page's only
// status), and on any error, a `404` included, it is simply left out.
import './scenes.css'

import { useProject } from './useProject'

export function BookHeader() {
  const { data, isPending } = useProject()
  if (data === undefined) {
    return isPending ? <div aria-hidden="true" className="book-premise-skeleton" /> : null
  }
  return (
    <div className="book-premise">
      <p className="book-statement">{data.premise.statement}</p>
      <p className="book-question">
        <span className="book-question-label">Pregunta dramática</span>
        <span>{data.premise.dramatic_question}</span>
      </p>
    </div>
  )
}
