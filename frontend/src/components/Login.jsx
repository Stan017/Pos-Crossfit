import { useState } from 'react'
import { Link } from 'react-router-dom'
import { authAPI } from '../services/api'
import { VERTICAL } from '../vertical'
import '@shared/components/Login.css'

export default function Login({ onLogin }) {
  const [gymSlug,  setGymSlug]  = useState('')
  const [email,    setEmail]    = useState('')
  const [password, setPassword] = useState('')
  const [error,    setError]    = useState('')
  const [cargando, setCargando] = useState(false)

  async function entrar(e) {
    e.preventDefault()
    if (cargando) return
    setCargando(true)
    setError('')
    try {
      const { data } = await authAPI.login({
        gym_slug: gymSlug.trim(),
        email:    email.trim(),
        password,
        vertical: VERTICAL,
      })
      onLogin(data)
    } catch (err) {
      const detail = err.response?.data?.detail
      if (err.response?.status === 401) {
        setError(detail || 'Credenciales inválidas.')
      } else if (err.response?.status === 402) {
        setError('Suscripción vencida. Contacta al administrador de la plataforma.')
      } else {
        setError(detail || 'Error al conectar con el servidor.')
      }
    } finally {
      setCargando(false)
    }
  }

  return (
    <div className="login-overlay">
      <form className="login-card" onSubmit={entrar}>

        <div className="login-logo">CrossFit</div>
        <p className="login-sub">Gestión de Box</p>

        <div className="login-field">
          <label>Box</label>
          <input
            type="text"
            autoComplete="off"
            autoCapitalize="none"
            value={gymSlug}
            onChange={e => { setGymSlug(e.target.value); setError('') }}
            placeholder="mi-box"
            required
          />
        </div>

        <div className="login-field">
          <label>Email</label>
          <input
            type="email"
            autoComplete="username"
            value={email}
            onChange={e => { setEmail(e.target.value); setError('') }}
            placeholder="admin@mibox.com"
            required
          />
        </div>

        <div className="login-field">
          <label>Contraseña</label>
          <input
            type="password"
            autoComplete="current-password"
            value={password}
            onChange={e => { setPassword(e.target.value); setError('') }}
            placeholder="••••••••"
            required
          />
        </div>

        {error && <p className="login-error">{error}</p>}

        <button
          type="submit"
          className="login-btn"
          disabled={!gymSlug || !email || !password || cargando}
        >
          {cargando ? 'Conectando…' : 'Entrar'}
        </button>

        <Link to="/registro" className="login-link">¿No tenés cuenta? Registrate</Link>

      </form>
    </div>
  )
}
