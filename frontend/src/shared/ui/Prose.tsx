// Store prose rendered as Markdown. Used by scenes/ and bible/: spec 003, FR-UI3, plan Q9
// (moved from scenes/, same API). Spec 002, FR-TOOL-05, AC 9; plan 002 P15.
// react-markdown with its defaults: no rehype-raw, so raw HTML in store content becomes text,
// never an element, and links carry no target=_blank. Store content is untrusted.
// A reading column of at most 70ch. The class stays `prose`: spec 002's tests select it.
import './Prose.css'

import Markdown from 'react-markdown'

export interface ProseProps {
  markdown: string
}

export function Prose({ markdown }: ProseProps) {
  return (
    <div className="prose">
      <Markdown>{markdown}</Markdown>
    </div>
  )
}
