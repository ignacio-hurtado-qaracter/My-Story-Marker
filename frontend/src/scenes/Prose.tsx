// Draft prose as Markdown. Spec 002, FR-TOOL-05, AC 9; plan decision P15.
// react-markdown with its defaults: no rehype-raw, so raw HTML in a draft becomes text, never an
// element, and links carry no target=_blank. Store content is untrusted.
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
