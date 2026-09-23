// The global layout: header, navigation, health badge, and the routed page. Spec 002, FR-SHELL-01.
import { Link, NavLink, Outlet } from 'react-router'

import { HealthBadge } from '../health'

export function Layout() {
  return (
    <>
      <header className="app-header">
        <Link to="/scenes" className="app-title">
          My Story Marker
        </Link>
        <nav aria-label="Principal">
          <ul>
            <li>
              <NavLink to="/scenes">Escenas</NavLink>
            </li>
            <li>
              <NavLink to="/graph3d">Grafo 3D</NavLink>
            </li>
          </ul>
        </nav>
        <HealthBadge />
      </header>
      <main>
        <Outlet />
      </main>
    </>
  )
}
