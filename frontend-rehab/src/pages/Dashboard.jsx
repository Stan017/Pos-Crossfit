import { useState, useEffect, useMemo } from 'react'
import { dashboardAPI } from '../services/api'
import { useNavigate } from 'react-router-dom'
import { useMonthNavigator } from '@shared/hooks/useMonthNavigator'
import { MESES } from '@shared/utils/fecha'
import '@shared/pages/Dashboard.css'

export default function Dashboard() {
  const { mes, anio, esMesActual, retroceder, avanzar } = useMonthNavigator()

  const [datos, setDatos]       = useState(null)
  const [cargando, setCargando] = useState(true)
  const [error, setError]       = useState(null)

  const navigate = useNavigate()

  // ─── Carga ──────────────────────────────────────────────────────────────────

  useEffect(() => {
    setCargando(true)
    setError(null)
    dashboardAPI.kpis(mes, anio)
      .then(r => setDatos(r.data))
      .catch(() => setError('No se pudo conectar con el servidor.'))
      .finally(() => setCargando(false))
  }, [mes, anio])

  // ─── Render ─────────────────────────────────────────────────────────────────

  const maxUnidades = useMemo(() =>
    datos?.top_productos?.length > 0
      ? Math.max(...datos.top_productos.map(p => p.unidades_vendidas))
      : 1
  , [datos?.top_productos])

  return (
    <div className="dashboard">

      {/* Header con navegación de meses */}
      <div className="page-header">
        <h1>Dashboard</h1>
        <div className="mes-nav">
          <button className="mes-btn" onClick={retroceder} title="Mes anterior">‹</button>
          <span className="mes-label">{MESES[mes - 1]} {anio}</span>
          <button
            className={`mes-btn ${esMesActual ? 'mes-btn-disabled' : ''}`}
            onClick={avanzar}
            disabled={esMesActual}
            title={esMesActual ? 'Es el mes actual' : 'Mes siguiente'}
          >›</button>
        </div>
      </div>

      {cargando && <p className="estado-msg">Cargando…</p>}
      {error    && <p className="estado-msg error">{error}</p>}

      {!cargando && !error && datos && (
        <>
          {/* KPI cards */}
          <div className="kpi-grid">

            <div
              className="kpi-card kpi-clientes kpi-clickable"
              onClick={() => navigate('/membresias')}
              title="Ver membresías"
            >
              <div className="kpi-icono"><span className="material-symbols-outlined">card_membership</span></div>
              <div className="kpi-body">
                <span className="kpi-label">Membresías activas</span>
                <span className="kpi-valor num">{datos.membresias_activas}</span>
                <span className="kpi-sub">→ ver membresías</span>
              </div>
            </div>

            <div
              className="kpi-card kpi-nuevos kpi-clickable"
              onClick={() => navigate('/miembros', { state: { filtro: 'nuevos', mes, anio } })}
              title="Ver pacientes nuevos de este mes"
            >
              <div className="kpi-icono"><span className="material-symbols-outlined">person_add</span></div>
              <div className="kpi-body">
                <span className="kpi-label">Nuevos este mes</span>
                <span className="kpi-valor num">{datos.nuevos_mes}</span>
                <span className="kpi-sub">→ ver pacientes</span>
              </div>
            </div>

            <div
              className="kpi-card kpi-alertas kpi-clickable"
              onClick={() => navigate('/membresias')}
              title="Ver alertas de vencimiento"
            >
              <div className="kpi-icono"><span className="material-symbols-outlined">warning</span></div>
              <div className="kpi-body">
                <span className="kpi-label">Alertas vencimiento</span>
                <span className="kpi-valor num">{datos.alertas}</span>
                <span className="kpi-sub">próximos 7 días</span>
              </div>
            </div>

            <div
              className="kpi-card kpi-asistencia kpi-clickable"
              onClick={() => navigate('/checkin')}
              title="Ver check-in"
            >
              <div className="kpi-icono"><span className="material-symbols-outlined">how_to_reg</span></div>
              <div className="kpi-body">
                <span className="kpi-label">Asistencias hoy</span>
                <span className="kpi-valor num">{datos.asistencias_hoy}</span>
                <span className="kpi-sub">→ ver check-in</span>
              </div>
            </div>

            {datos.revenue_mes !== null && (
              <div className="kpi-card kpi-ventas">
                <div className="kpi-icono"><span className="material-symbols-outlined">payments</span></div>
                <div className="kpi-body">
                  <span className="kpi-label">Revenue del mes</span>
                  <span className="kpi-valor num">${datos.revenue_mes.toFixed(2)}</span>
                  <span className="kpi-sub">{datos.ventas_mes} ventas</span>
                </div>
              </div>
            )}

            <div
              className="kpi-card kpi-abonos kpi-clickable"
              onClick={() => navigate('/abonos')}
              title="Ver abonos"
            >
              <div className="kpi-icono"><span className="material-symbols-outlined">credit_score</span></div>
              <div className="kpi-body">
                <span className="kpi-label">Deuda total</span>
                <span className="kpi-valor num">${parseFloat(datos.deuda_total ?? 0).toFixed(2)}</span>
                <span className="kpi-sub">→ ver abonos</span>
              </div>
            </div>

            <div
              className="kpi-card kpi-sinmov kpi-clickable"
              onClick={() => navigate('/inventario')}
              title="Ver inventario"
            >
              <div className="kpi-icono"><span className="material-symbols-outlined">inventory_2</span></div>
              <div className="kpi-body">
                <span className="kpi-label">Stock bajo</span>
                <span className="kpi-valor num">{datos.stock_bajo}</span>
                <span className="kpi-sub">productos en alerta</span>
              </div>
            </div>

          </div>

          {/* Top productos */}
          <div className="dash-section">
            <h2 className="section-titulo">Top productos — {MESES[mes - 1]} {anio}</h2>

            {datos.top_productos.length === 0 ? (
              <div className="top-vacio">
                <span>Sin ventas registradas en {MESES[mes - 1]}.</span>
              </div>
            ) : (
              <ul className="top-lista">
                {datos.top_productos.map((p, i) => {
                  const pct = Math.round((p.unidades_vendidas / maxUnidades) * 100)
                  return (
                    <li key={`${p.nombre}-${p.categoria}`} className="top-row">
                      <span className="top-rank num">#{i + 1}</span>
                      <div className="top-info">
                        <span className="top-nombre">{p.nombre}</span>
                        {p.categoria && <span className="top-marca">{p.categoria}</span>}
                      </div>
                      <div className="top-barra-wrap">
                        <div className="top-barra">
                          <div className="top-barra-fill" style={{ width: `${pct}%` }} />
                        </div>
                      </div>
                      <div className="top-nums">
                        <span className="num top-uds">{p.unidades_vendidas} uds</span>
                        <span className="num top-total">${p.total_vendido.toFixed(2)}</span>
                      </div>
                    </li>
                  )
                })}
              </ul>
            )}
          </div>
        </>
      )}

    </div>
  )
}
