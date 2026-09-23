// The page for an unknown route, rendered inside the layout. Spec 002, FR-SHELL-03.
// Static: no loading, empty or error state applies.
import { Link } from 'react-router'

import { Heading } from '../shared/ui'

export function NotFoundPage() {
  return (
    <section>
      <Heading>Página no encontrada</Heading>
      <p>La dirección que has abierto no corresponde a ninguna página.</p>
      <Link to="/scenes">Volver a las escenas</Link>
    </section>
  )
}
