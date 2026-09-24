// The global layout: header, navigation, health badge, and the routed page. Spec 002, FR-SHELL-01.
import { Link, NavLink, Outlet } from 'react-router'

import { HealthBadge } from '../health'

// WCAG 2.2 AA 2.5.8: stacked navigation links need a 24 px target (spec 002, NFR-02, AC 11).
const TARGET = { display: 'inline-block', minHeight: '24px', padding: '4px 0' } as const

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
              <NavLink to="/scenes" style={TARGET}>
                Escenas
              </NavLink>
            </li>
            <li>
              <NavLink to="/graph3d" style={TARGET}>
                Grafo 3D
              </NavLink>
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
