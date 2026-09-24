// The state of a reader page when the novel has no published version yet. Spec 014.
import { Link } from 'react-router'

export function NoVersion() {
  return (
    <p className="reader-state">
      Esta novela aún no tiene ninguna versión publicada. <Link to="/">Volver a las novelas</Link>
    </p>
  )
}
