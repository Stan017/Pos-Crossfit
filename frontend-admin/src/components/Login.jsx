import { useState, useEffect } from 'react'
import { analyticsAPI, setClave, borrarClave } from '../services/api'
import './Login.css'

// Fricción visual entre reintentos — NO es la defensa real (esa vive en el
// backend, platform_admin.py, que bloquea por IP sin importar qué cliente
// pegue). Esto solo desalienta probar claves a mano rápido y seguido; con
// curl directo al backend, este cooldown no existe.
const COOLDOWNS_POR_FALLO = [0, 0, 2, 4, 8, 8, 8, 8, 8, 8]

export default function Login({ onLogin }) {
  const [clave, setClaveInput] = useState('')
  const [verificando, setVerificando] = useState(false)
  const [error, setError] = useState(null)
  const [fallos, setFallos] = useState(0)
  const [segundosRestantes, setSegundosRestantes] = useState(0)

  useEffect(() => {
    if (segundosRestantes <= 0) return
    const t = setTimeout(() => setSegundosRestantes(s => s - 1), 1000)
    return () => clearTimeout(t)
  }, [segundosRestantes])

  async function entrar(e) {
    e.preventDefault()
    if (!clave.trim() || segundosRestantes > 0) return

    setVerificando(true)
    setError(null)
    setClave(clave.trim())
    try {
      await analyticsAPI.ping()
      onLogin()
    } catch (err) {
      borrarClave()
      if (err.response?.status === 429) {
        setError('Demasiados intentos fallidos. Esperá un minuto e intentá de nuevo.')
        setSegundosRestantes(60)
      } else if (err.response?.status === 403) {
        const nuevosFallos = fallos + 1
        setFallos(nuevosFallos)
        setError('Clave incorrecta.')
        setSegundosRestantes(COOLDOWNS_POR_FALLO[Math.min(nuevosFallos, COOLDOWNS_POR_FALLO.length - 1)])
      } else if (err.response?.status === 503) {
        setError('El panel de plataforma no está configurado en el servidor.')
      } else {
        setError('No se pudo conectar con el servidor.')
      }
    } finally {
      setVerificando(false)
    }
  }

  return (
    <div className="login-page">
      <form className="login-card" onSubmit={entrar}>
        <div className="login-logo">DarkCross</div>
        <p className="login-subtitulo">Panel de plataforma</p>

        <label>
          <span className="label-text">Clave de plataforma</span>
          <input
            type="password"
            value={clave}
            onChange={e => setClaveInput(e.target.value)}
            autoFocus
            required
          />
        </label>

        {error && <p className="login-error">{error}</p>}

        <button type="submit" className="btn-primario" disabled={verificando || segundosRestantes > 0}>
          {verificando ? 'Verificando…' : segundosRestantes > 0 ? `Esperá ${segundosRestantes}s…` : 'Entrar'}
        </button>
      </form>
    </div>
  )
}
