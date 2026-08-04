import { useState, useEffect, useCallback } from 'react'
import { analyticsAPI, suscripcionesAdminAPI } from '../services/api'
import { estadoSaasBadge, fmtPlanSaas, fmtTierSaas, fmtVertical, formatFecha, formatFechaHora } from '../utils/formato'
import './Clientes.css'
import './Gyms.css'

const TIERS = ['trial', 'solo', 'estandar', 'clinica', 'personalizado']

export default function Gyms() {
  const [gyms, setGyms]         = useState([])
  const [cargando, setCargando] = useState(true)
  const [error, setError]       = useState(null)
  const [accionando, setAccionando] = useState(null)  // id del gym con una mutación en curso

  const cargar = useCallback(async () => {
    try {
      setCargando(true)
      setError(null)
      const res = await analyticsAPI.gyms()
      setGyms(res.data)
    } catch {
      setError('No se pudo conectar con el servidor.')
    } finally {
      setCargando(false)
    }
  }, [])

  useEffect(() => { cargar() }, [cargar])

  async function cambiarTier(gym, tier) {
    if (tier === gym.saas_tier) return
    setAccionando(gym.id)
    try {
      await suscripcionesAdminAPI.cambiarTier(gym.id, tier)
      await cargar()
    } catch (err) {
      alert(err.response?.data?.detail ?? 'No se pudo cambiar el tier.')
    } finally {
      setAccionando(null)
    }
  }

  async function alternarSuspension(gym) {
    const suspendido = gym.saas_estado === 'suspendida'
    const confirmacion = suspendido
      ? `¿Reactivar "${gym.nombre}"?`
      : `¿Suspender "${gym.nombre}"? Pierde acceso inmediatamente.`
    if (!confirm(confirmacion)) return

    setAccionando(gym.id)
    try {
      if (suspendido) {
        await suscripcionesAdminAPI.reactivar(gym.id)
      } else {
        await suscripcionesAdminAPI.suspender(gym.id, null)
      }
      await cargar()
    } catch (err) {
      alert(err.response?.data?.detail ?? 'No se pudo actualizar el establecimiento.')
    } finally {
      setAccionando(null)
    }
  }

  return (
    <div className="page">
      <div className="page-header">
        <h1>Establecimientos</h1>
        <span className="total-label">{gyms.length} establecimiento{gyms.length === 1 ? '' : 's'}</span>
      </div>

      {error && <p className="mensaje-error">{error}</p>}

      {cargando ? (
        <p className="cargando">Cargando...</p>
      ) : gyms.length === 0 ? (
        <p className="vacio">No hay establecimientos registrados todavía.</p>
      ) : (
        <div className="tabla-wrapper">
          <table className="tabla tabla-gyms">
            <thead>
              <tr>
                <th>Nombre</th>
                <th>Vertical</th>
                <th>Estado</th>
                <th>Plan</th>
                <th>Vence</th>
                <th>Tier</th>
                <th>Usuarios</th>
                <th>Instructores</th>
                <th>Miembros</th>
                <th>Ventas del mes</th>
                <th>Última actividad</th>
                <th>Acciones</th>
              </tr>
            </thead>
            <tbody>
              {gyms.map(g => {
                const badge = estadoSaasBadge(g.saas_estado)
                const suspendido = g.saas_estado === 'suspendida'
                return (
                  <tr key={g.id}>
                    <td className="td-nombre">
                      {g.nombre}
                      <div className="text-muted td-sub">{g.email}</div>
                    </td>
                    <td>{fmtVertical(g.vertical)}</td>
                    <td><span className={`badge ${badge.clase}`}>{badge.label}</span></td>
                    <td>{fmtPlanSaas(g.saas_plan)}</td>
                    <td>
                      {formatFecha(g.saas_vence_en)}
                      {g.dias_restantes !== null && (
                        <div className="text-muted td-sub">{g.dias_restantes}d</div>
                      )}
                    </td>
                    <td>
                      <select
                        value={g.saas_tier}
                        onChange={e => cambiarTier(g, e.target.value)}
                        disabled={accionando === g.id}
                      >
                        {TIERS.map(t => <option key={t} value={t}>{fmtTierSaas(t)}</option>)}
                      </select>
                    </td>
                    <td className="num">{g.usuarios_total} <span className="text-muted">({g.usuarios_admin}A/{g.usuarios_staff}S)</span></td>
                    <td className="num">
                      {g.instructores_total}
                      <div className="text-muted td-sub">
                        {g.instructores_por_tipo.entrenador}E / {g.instructores_por_tipo.doctor}D / {g.instructores_por_tipo.asistente}As
                      </div>
                    </td>
                    <td className="num">{g.miembros_activos} <span className="text-muted">/ {g.miembros_total}</span></td>
                    <td className="num">
                      ${g.ventas_mes_actual.monto.toFixed(2)}
                      <div className="text-muted td-sub">{g.ventas_mes_actual.cantidad} ventas</div>
                    </td>
                    <td className="text-muted">{formatFechaHora(g.ultima_actividad)}</td>
                    <td className="td-acciones">
                      <button
                        className={`btn btn-sm ${suspendido ? 'btn-primary' : 'btn-danger'}`}
                        onClick={() => alternarSuspension(g)}
                        disabled={accionando === g.id}
                      >
                        {suspendido ? 'Reactivar' : 'Suspender'}
                      </button>
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}
