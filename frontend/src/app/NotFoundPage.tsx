// The page for an unknown route, rendered inside the layout. Spec 002, FR-SHELL-03.
// Static: no loading, empty or error state applies. Look: spec 003, FR-SHELL3-05.
import { Link } from 'react-router'

import { Heading } from '../shared/ui'
import './Layout.css'

export function NotFoundPage() {
  return (
    <section className="not-found card">
      <p className="eyebrow">Error 404</p>
      <Heading>Página no encontrada</Heading>
      <p className="not-found-text">La dirección que has abierto no corresponde a ninguna página.</p>
      <Link to="/" className="btn-ghost">
        Volver a la biblioteca
      </Link>
    </section>
  )
}
