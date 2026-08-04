import { useState, useEffect } from 'react'
import { analyticsAPI } from '../services/api'
import { estadoSaasBadge, fmtVertical } from '../utils/formato'
import './Dashboard.css'

export default function Dashboard() {
  const [r, setR]             = useState(null)
  const [cargando, setCargando] = useState(true)
  const [error, setError]     = useState(null)

  useEffect(() => {
    analyticsAPI.resumen()
      .then(res => setR(res.data))
      .catch(() => setError('No se pudo cargar el resumen.'))
      .finally(() => setCargando(false))
  }, [])

  if (cargando) return <p className="estado-msg">Cargando…</p>
  if (error)     return <p className="form-error">{error}</p>
  if (!r)        return null

  return (
    <div className="dashboard-admin">
      <div className="page-header">
        <h1>Dashboard</h1>
      </div>

      <div className="kpi-grid">
        <div className="kpi-card">
          <span className="kpi-valor num">{r.gyms_total}</span>
          <span className="kpi-label">Establecimientos</span>
        </div>
        <div className="kpi-card">
          <span className="kpi-valor num">{r.usuarios_total}</span>
          <span className="kpi-label">Usuarios de staff</span>
        </div>
        <div className="kpi-card">
          <span className="kpi-valor num">{r.instructores_total}</span>
          <span className="kpi-label">Instructores</span>
        </div>
        <div className="kpi-card">
          <span className="kpi-valor num">{r.miembros_activos}</span>
          <span className="kpi-label">Miembros activos <span className="text-muted">/ {r.miembros_total}</span></span>
        </div>
        <div className="kpi-card">
          <span className="kpi-valor num">${r.ventas_mes_actual.monto.toFixed(2)}</span>
          <span className="kpi-label">Ventas este mes <span className="text-muted">({r.ventas_mes_actual.cantidad})</span></span>
        </div>
        <div className="kpi-card kpi-destacado">
          <span className="kpi-valor num">${r.revenue_saas_mes_actual.toFixed(2)}</span>
          <span className="kpi-label">Revenue SaaS este mes</span>
        </div>
        <div className="kpi-card">
          <span className="kpi-valor num">${r.revenue_saas_historico.toFixed(2)}</span>
          <span className="kpi-label">Revenue SaaS histórico</span>
        </div>
      </div>

      <div className="desglose-grid">
        <div className="desglose-card">
          <h2>Establecimientos por vertical</h2>
          <ul className="desglose-lista">
            {Object.entries(r.gyms_por_vertical).map(([v, n]) => (
              <li key={v}><span>{fmtVertical(v)}</span><span className="num">{n}</span></li>
            ))}
          </ul>
        </div>

        <div className="desglose-card">
          <h2>Establecimientos por estado de suscripción</h2>
          <ul className="desglose-lista">
            {Object.entries(r.gyms_por_estado_saas).map(([e, n]) => (
              <li key={e}><span>{estadoSaasBadge(e).label}</span><span className="num">{n}</span></li>
            ))}
          </ul>
        </div>

        <div className="desglose-card">
          <h2>Instructores por tipo</h2>
          <ul className="desglose-lista">
            <li><span>Entrenador</span><span className="num">{r.instructores_por_tipo.entrenador}</span></li>
            <li><span>Doctor</span><span className="num">{r.instructores_por_tipo.doctor}</span></li>
            <li><span>Asistente</span><span className="num">{r.instructores_por_tipo.asistente}</span></li>
          </ul>
        </div>
      </div>
    </div>
  )
}
