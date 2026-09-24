// The global layout: header, navigation, health badge, the routed page and the footer.
// Spec 002, FR-SHELL-01; look from spec 003, FR-SHELL3-01..04.
import { Link, NavLink, Outlet } from 'react-router'

import { HealthBadge } from '../health'
import './Layout.css'
import logo from './logo-qaracter.svg'

export function Layout() {
  return (
    <>
      <header className="app-header">
        <div className="app-header-inner">
          {/* The logo is decorative (alt=""), so the link's name stays "My Story Marker". */}
          <Link to="/scenes" className="app-brand">
            <img src={logo} alt="" className="app-brand-logo" width={153} height={36} />
            <span className="app-brand-divider" aria-hidden="true" />
            <span className="app-brand-product">
              My Story <span>Marker</span>
            </span>
          </Link>
          <nav aria-label="Principal" className="app-nav">
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
        </div>
      </header>
      <main className="container">
        <Outlet />
      </main>
      <footer className="app-footer">
        <p>My Story Marker · Qaracter</p>
      </footer>
    </>
  )
}
