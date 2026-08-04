import { useState } from 'react'
import { Link } from 'react-router-dom'
import { authAPI } from '../services/api'
import { VERTICAL } from '../vertical'
import '@shared/components/Login.css'

export default function Registro({ onRegistrado }) {
  const [gymNombre,       setGymNombre]       = useState('')
  const [gymSlug,         setGymSlug]         = useState('')
  const [gymEmail,        setGymEmail]        = useState('')
  const [nombre,          setNombre]          = useState('')
  const [apellido,        setApellido]        = useState('')
  const [fechaNac,        setFechaNac]        = useState('')
  const [email,           setEmail]           = useState('')
  const [password,        setPassword]        = useState('')
  const [passwordConfirm, setPasswordConfirm] = useState('')
  const [mostrarPassword, setMostrarPassword] = useState(false)
  const [error,           setError]           = useState('')
  const [cargando,        setCargando]        = useState(false)

  const passwordsNoCoinciden = password && passwordConfirm && password !== passwordConfirm

  async function registrar(e) {
    e.preventDefault()
    if (cargando) return
    setCargando(true)
    setError('')
    try {
      const { data } = await authAPI.registerGym({
        gym_nombre:             gymNombre.trim(),
        gym_slug:               gymSlug.trim(),
        gym_email:              gymEmail.trim(),
        admin_nombre:           nombre.trim(),
        admin_apellido:         apellido.trim(),
        admin_fecha_nacimiento: fechaNac,
        admin_email:            email.trim(),
        admin_password:         password,
        vertical:               VERTICAL,
      })
      onRegistrado(data)
    } catch (err) {
      const detail = err.response?.data?.detail
      if (err.response?.status === 409) {
        setError(detail || 'Ese box o email ya está registrado.')
      } else {
        setError(detail || 'Error al conectar con el servidor.')
      }
    } finally {
      setCargando(false)
    }
  }

  const completo = gymNombre && gymSlug && gymEmail && nombre && apellido && fechaNac
    && email && password && passwordConfirm && !passwordsNoCoinciden

  return (
    <div className="login-overlay">
      <form className="login-card registro" onSubmit={registrar}>

        <div className="login-logo">CrossFit</div>
        <p className="login-sub">Creá tu cuenta — <span className="login-highlight">10 días de prueba</span></p>

        <div className="registro-grid">

          <div className="login-field">
            <label>Nombre del box</label>
            <input
              type="text"
              value={gymNombre}
              onChange={e => { setGymNombre(e.target.value); setError('') }}
              placeholder="Escribí el nombre del box"
              required
            />
          </div>

          <div className="login-field">
            <label>Email del negocio</label>
            <input
              type="email"
              value={gymEmail}
              onChange={e => { setGymEmail(e.target.value); setError('') }}
              placeholder="demo@demo.com"
              required
            />
          </div>

          <div className="login-field">
            <label>Slug (así te identifica el sistema)</label>
            <input
              type="text"
              autoCapitalize="none"
              value={gymSlug}
              onChange={e => { setGymSlug(e.target.value); setError('') }}
              placeholder="Escribí el slug"
              required
            />
          </div>

          <div className="login-field">
            <label>Tu nombre</label>
            <input
              type="text"
              value={nombre}
              onChange={e => { setNombre(e.target.value); setError('') }}
              placeholder="Escribí tu nombre"
              required
            />
          </div>

          <div className="login-field">
            <label>Tu apellido</label>
            <input
              type="text"
              value={apellido}
              onChange={e => { setApellido(e.target.value); setError('') }}
              placeholder="Escribí tu apellido"
              required
            />
          </div>

          <div className="login-field">
            <label>Fecha de nacimiento</label>
            <input
              type="date"
              value={fechaNac}
              onChange={e => { setFechaNac(e.target.value); setError('') }}
              required
            />
          </div>

          <div className="login-field login-field-full">
            <label>Tu email (para entrar)</label>
            <input
              type="email"
              autoComplete="username"
              value={email}
              onChange={e => { setEmail(e.target.value); setError('') }}
              placeholder="demo@demobox.com"
              required
            />
          </div>

          <div className="login-field">
            <label>Contraseña</label>
            <div className="login-field-password">
              <input
                type={mostrarPassword ? 'text' : 'password'}
                autoComplete="new-password"
                minLength={8}
                value={password}
                onChange={e => { setPassword(e.target.value); setError('') }}
                placeholder="••••••••"
                required
              />
              <button
                type="button"
                className="toggle-password"
                onClick={() => setMostrarPassword(m => !m)}
                aria-label={mostrarPassword ? 'Ocultar contraseña' : 'Mostrar contraseña'}
                tabIndex={-1}
              >
                <span className="material-symbols-outlined">
                  {mostrarPassword ? 'visibility_off' : 'visibility'}
                </span>
              </button>
            </div>
          </div>

          <div className="login-field">
            <label>Confirmar contraseña</label>
            <div className="login-field-password">
              <input
                type={mostrarPassword ? 'text' : 'password'}
                autoComplete="new-password"
                minLength={8}
                value={passwordConfirm}
                onChange={e => { setPasswordConfirm(e.target.value); setError('') }}
                placeholder="••••••••"
                required
              />
            </div>
          </div>

        </div>

        {passwordsNoCoinciden && <p className="login-error">Las contraseñas no coinciden.</p>}
        {error && <p className="login-error">{error}</p>}

        <button
          type="submit"
          className="login-btn"
          disabled={!completo || cargando}
        >
          {cargando ? 'Creando cuenta…' : 'Crear cuenta'}
        </button>

        <Link to="/" className="login-link">Ya tengo cuenta — iniciar sesión</Link>

      </form>
    </div>
  )
}
