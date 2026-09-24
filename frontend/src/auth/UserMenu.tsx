// The header's session control (spec 018): the email and "Salir" while logged in, "Entrar"
// otherwise. `AuthRedirect` sends the reader to the login page when the API answers 401.
import { useEffect } from 'react'
import { Link, useLocation, useNavigate } from 'react-router'

import { onUnauthorized, setAuthToken } from '../shared/api'
import { useAuthToken, useLogout, useMe } from './api'
import './auth.css'

export function UserMenu() {
  const token = useAuthToken()
  const me = useMe(token)
  const logout = useLogout()
  const navigate = useNavigate()
  if (!token) {
    return (
      <Link to="/login" className="btn-ghost auth-menu-link">
        Entrar
      </Link>
    )
  }
  return (
    <div className="auth-menu">
      {me.data === undefined ? null : <span className="auth-menu-email">{me.data.email}</span>}
      <button
        type="button"
        className="btn-ghost"
        onClick={() => {
          logout()
          void navigate('/login')
        }}
      >
        Salir
      </button>
    </div>
  )
}

export function AuthRedirect() {
  const navigate = useNavigate()
  const { pathname } = useLocation()
  useEffect(
    () =>
      onUnauthorized(() => {
        if (pathname === '/login') return
        setAuthToken(null)
        void navigate(`/login?next=${encodeURIComponent(pathname)}`, { replace: true })
      }),
    [navigate, pathname],
  )
  return null
}
