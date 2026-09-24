// The login and register page (spec 018): one form, two modes. On success the reader goes
// back to the page that asked for a login (`?next=`), or to the novels.
import { useId, useState, type SubmitEvent } from 'react'
import { useNavigate, useSearchParams } from 'react-router'

import { useAuthenticate, type Mode } from './api'
import './auth.css'

function text(data: FormData, name: string): string {
  const value = data.get(name)
  return typeof value === 'string' ? value : ''
}

function safeNext(next: string | null): string {
  // Only paths of this app: never an absolute URL or a protocol-relative one.
  return next !== null && next.startsWith('/') && !next.startsWith('//') ? next : '/'
}

export function LoginPage() {
  const id = useId()
  const [mode, setMode] = useState<Mode>('login')
  const [params] = useSearchParams()
  const navigate = useNavigate()
  const authenticate = useAuthenticate(mode)

  function handleSubmit(event: SubmitEvent<HTMLFormElement>) {
    event.preventDefault()
    const form = new FormData(event.currentTarget)
    authenticate.mutate(
      { email: text(form, 'email'), password: text(form, 'password') },
      { onSuccess: () => void navigate(safeNext(params.get('next')), { replace: true }) },
    )
  }

  const title = mode === 'login' ? 'Entrar' : 'Crear cuenta'
  return (
    <section className="auth card" aria-labelledby={`${id}-title`}>
      <h1 id={`${id}-title`} className="auth-title">
        {title}
      </h1>
      <p className="auth-hint">Cada cuenta ve solo sus propias novelas.</p>
      <form onSubmit={handleSubmit} className="auth-form">
        <label htmlFor={`${id}-email`}>Email</label>
        <input id={`${id}-email`} name="email" type="email" autoComplete="email" required maxLength={254} />
        <label htmlFor={`${id}-password`}>Contraseña</label>
        <input
          id={`${id}-password`}
          name="password"
          type="password"
          autoComplete={mode === 'login' ? 'current-password' : 'new-password'}
          required
          minLength={8}
          maxLength={72}
        />
        <div className="auth-actions">
          <button type="submit" className="auth-btn-primary" disabled={authenticate.isPending}>
            {title}
          </button>
          <button
            type="button"
            className="btn-ghost"
            onClick={() => {
              authenticate.reset()
              setMode(mode === 'login' ? 'register' : 'login')
            }}
          >
            {mode === 'login' ? 'Crear una cuenta' : 'Ya tengo cuenta'}
          </button>
        </div>
      </form>
      <div role="status" className="auth-status">
        {authenticate.isError ? <p>{authenticate.error.message}</p> : null}
      </div>
    </section>
  )
}
