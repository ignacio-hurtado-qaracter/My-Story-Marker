// The global layout: header, navigation, health badge, the routed page and the footer.
// Spec 002, FR-SHELL-01; spec 003, FR-IA-02 (revision 2).
import { Link, Outlet, useLocation } from 'react-router'

import { AuthRedirect, UserMenu } from '../auth'
import { HealthBadge } from '../health'
import './Layout.css'
import logo from './logo-qaracter.svg'

interface NavItem {
  label: string
  to: string
  /** The paths this item stands for: the exact path, or any path below one of the prefixes. */
  exact?: string
  prefixes?: readonly string[]
}

// Spec 014: the reader's own navigation (Portada, Índice, Personajes y lugares, versions)
// lives inside each novel; the shell lists the novels and keeps the harness's scene pages.
const NAV: readonly NavItem[] = [
  { label: 'Novelas', to: '/', exact: '/', prefixes: ['/novelas'] },
  { label: 'Nueva novela', to: '/nueva', prefixes: ['/nueva'] },
  { label: 'Cómo funciona', to: '/arquitectura', exact: '/arquitectura' },
]

function isCurrent(item: NavItem, pathname: string): boolean {
  if (item.exact !== undefined && pathname === item.exact) return true
  return (item.prefixes ?? []).some((prefix) => pathname === prefix || pathname.startsWith(`${prefix}/`))
}

export function Layout() {
  const { pathname } = useLocation()
  return (
    <>
      <header className="app-header">
        <div className="app-header-inner">
          {/* The logo is decorative (alt=""), so the link's name stays "My Story Marker". */}
          <Link to="/" className="app-brand">
            <img src={logo} alt="" className="app-brand-logo" width={153} height={36} />
            <span className="app-brand-divider" aria-hidden="true" />
            <span className="app-brand-product">
              My Story <span>Marker</span>
            </span>
          </Link>
          <nav aria-label="Principal" className="app-nav">
            <ul>
              {NAV.map((item) => (
                <li key={item.to}>
                  <Link to={item.to} aria-current={isCurrent(item, pathname) ? 'page' : undefined}>
                    {item.label}
                  </Link>
                </li>
              ))}
            </ul>
          </nav>
          <HealthBadge />
          <UserMenu />
        </div>
      </header>
      <AuthRedirect />
      <main className="container">
        <Outlet />
      </main>
      <footer className="app-footer">
        <p>
          My Story Marker · Qaracter · <Link to="/graph3d">Vista 3D</Link>
        </p>
      </footer>
    </>
  )
}
