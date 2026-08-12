import { useState, useEffect, useRef } from 'react'
import { checkinAPI, miembrosAPI, horariosAPI } from '../services/api'
import { formatFechaHora, hoyLocal } from '@shared/utils/fecha'
import '@shared/pages/Clientes.css'

export default function CheckIn() {
  const [clases,               setClases]               = useState([])
  const [cargandoClases,       setCargandoClases]       = useState(true)
  const [errorClases,          setErrorClases]          = useState(null)
  const [claseSeleccionada,    setClaseSeleccionada]    = useState(null)
  const [reservaciones,        setReservaciones]        = useState([])
  const [cargandoReservaciones,setCargandoReservaciones]= useState(false)
  const [resultadosPorMiembro, setResultadosPorMiembro] = useState({}) // { miembro_id: {ok, mensaje} }

  const [busqueda,    setBusqueda]    = useState('')
  const [sugerencias, setSugerencias] = useState([])
  const [buscando,    setBuscando]    = useState(false)
  const [miembro,     setMiembro]     = useState(null)
  const [resultado,   setResultado]   = useState(null)
  const [cargando,    setCargando]    = useState(false)

  const [asistencias, setAsistencias] = useState([])
  const [cargandoLog, setCargandoLog] = useState(true)
  const [errorLog,    setErrorLog]    = useState(null)
  const [fechaDesde,  setFechaDesde]  = useState(hoyLocal())
  const [fechaHasta,  setFechaHasta]  = useState(hoyLocal())

  const inputRef     = useRef(null)
  const limpiarTimer = useRef(null)
  const cargarLogId  = useRef(0)

  useEffect(() => {
    cargarClases()
    return () => { if (limpiarTimer.current) clearTimeout(limpiarTimer.current) }
  }, [])

  useEffect(() => {
    cargarLog()
  }, [fechaDesde, fechaHasta])

  async function cargarClases() {
    try {
      setCargandoClases(true)
      setErrorClases(null)
      const hoy = hoyLocal()
      const res = await horariosAPI.listarClases({ fecha: hoy })
      setClases(res.data)
    } catch {
      setClases([])
      setErrorClases('No se pudieron cargar las clases de hoy.')
    } finally {
      setCargandoClases(false)
    }
  }

  async function seleccionarClase(clase) {
    if (clase.estado === 'cancelada') return
    setClaseSeleccionada(clase)
    setMiembro(null)
    setBusqueda('')
    setSugerencias([])
    setResultado(null)
    setResultadosPorMiembro({})
    setReservaciones([])
    setCargandoReservaciones(true)
    try {
      const res = await horariosAPI.listarReservaciones(clase.id)
      setReservaciones(res.data)
    } catch (err) {
      const detail = err.response?.data?.detail ?? 'Error cargando reservaciones.'
      setResultadosPorMiembro({ _error: detail })
    } finally {
      setCargandoReservaciones(false)
    }
    setTimeout(() => inputRef.current?.focus(), 50)
  }

  async function cargarLog() {
    // Guard de respuesta obsoleta: si cambiás fechaDesde y fechaHasta rápido
    // se disparan dos requests, y el más viejo puede resolver después del más
    // nuevo. idPropio solo aplica el resultado si nadie arrancó una carga más
    // nueva mientras esta estaba en vuelo.
    const idPropio = ++cargarLogId.current
    try {
      setCargandoLog(true)
      setErrorLog(null)
      const res = await checkinAPI.listar({ fecha_desde: fechaDesde, fecha_hasta: fechaHasta })
      if (idPropio !== cargarLogId.current) return
      setAsistencias(res.data)
    } catch {
      if (idPropio !== cargarLogId.current) return
      setErrorLog('No se pudo cargar el log de asistencias.')
    } finally {
      if (idPropio === cargarLogId.current) setCargandoLog(false)
    }
  }

  function irAHoyLog() {
    setFechaDesde(hoyLocal())
    setFechaHasta(hoyLocal())
  }

  // Autocompletado de miembros
  useEffect(() => {
    if (!busqueda.trim()) { setSugerencias([]); return }
    let ignore = false
    const t = setTimeout(async () => {
      try {
        setBuscando(true)
        const res = await miembrosAPI.listar({ q: busqueda, activo: true })
        if (!ignore) setSugerencias(res.data.slice(0, 8))
      } catch {
        if (!ignore) setSugerencias([])
      } finally {
        if (!ignore) setBuscando(false)
      }
    }, 250)
    return () => { ignore = true; clearTimeout(t) }
  }, [busqueda])

  function seleccionar(m) {
    setMiembro(m)
    setBusqueda(`${m.nombre} ${m.apellido}`)
    setSugerencias([])
    setResultado(null)
  }

  function limpiarMiembro() {
    setMiembro(null)
    setBusqueda('')
    setSugerencias([])
    setResultado(null)
    inputRef.current?.focus()
  }

  const reservadoIds = new Set(reservaciones.map(r => r.miembro_id))
  const esHoyLog = fechaDesde === hoyLocal() && fechaHasta === hoyLocal()

  async function registrarDirecto(miembro_id) {
    if (!claseSeleccionada) return
    setResultadosPorMiembro(prev => ({ ...prev, [miembro_id]: null }))
    try {
      setCargando(true)
      await checkinAPI.registrar({ miembro_id, clase_id: claseSeleccionada.id })
      setResultadosPorMiembro(prev => ({ ...prev, [miembro_id]: { ok: true } }))
      cargarLog()
      try {
        const r2 = await horariosAPI.listarReservaciones(claseSeleccionada.id)
        setReservaciones(r2.data)
      } catch {}
    } catch (err) {
      const detail = err.response?.data?.detail ?? 'Error al registrar el check-in.'
      setResultadosPorMiembro(prev => ({ ...prev, [miembro_id]: { ok: false, mensaje: detail } }))
    } finally {
      setCargando(false)
    }
  }

  async function registrar() {
    if (!miembro || !claseSeleccionada) return
    try {
      setCargando(true)
      setResultado(null)
      const res = await checkinAPI.registrar({ miembro_id: miembro.id, clase_id: claseSeleccionada.id })
      const advertencia = res.data?.advertencia ?? null
      setResultado({
        ok: true,
        advertencia,
        mensaje: `Check-in registrado para ${miembro.nombre} ${miembro.apellido}.`,
      })
      cargarLog()
      // Refrescar reservaciones y conteo de cupos
      try {
        const r2 = await horariosAPI.listarReservaciones(claseSeleccionada.id)
        setReservaciones(r2.data)
      } catch {}
      cargarClases()
      if (limpiarTimer.current) clearTimeout(limpiarTimer.current)
      limpiarTimer.current = setTimeout(limpiarMiembro, advertencia ? 4000 : 1800)
    } catch (err) {
      const detail = err.response?.data?.detail ?? 'Error al registrar el check-in.'
      setResultado({ ok: false, advertencia: null, mensaje: detail })
    } finally {
      setCargando(false)
    }
  }

  return (
    <div className="page clientes">
      <div className="page-header">
        <h1>Check-in</h1>
      </div>

      {/* ─── Paso 1: Seleccionar clase ─────────────────────────────────────────── */}
      <div className="checkin-step-section">
        <p className="checkin-step-label">1 · Selecciona la clase</p>
        {cargandoClases ? (
          <p className="cargando">Cargando clases...</p>
        ) : errorClases ? (
          <p className="estado-msg error">{errorClases}</p>
        ) : clases.length === 0 ? (
          <p className="vacio">No hay clases programadas para hoy. Crea una en <strong>Horarios</strong>.</p>
        ) : (
          <div className="checkin-clases-grid">
            {clases.map(c => (
              <button
                key={c.id}
                className={`checkin-clase-card${claseSeleccionada?.id === c.id ? ' seleccionada' : ''}${c.estado === 'cancelada' ? ' cancelada' : ''}`}
                onClick={() => seleccionarClase(c)}
                disabled={c.estado === 'cancelada'}
              >
                <span className="clase-card-nombre">{c.nombre}</span>
                <span className="clase-card-hora">{c.hora_inicio} – {c.hora_fin}</span>
                {c.instructor && <span className="clase-card-coach">{c.instructor.nombre}</span>}
                <span className="clase-card-cupo">{c.reservados}/{c.capacidad} reservados</span>
                {c.estado === 'cancelada' && <span className="clase-card-cancelada">Cancelada</span>}
              </button>
            ))}
          </div>
        )}
      </div>

      {/* ─── Paso 2: Reservados + walk-in ─────────────────────────────────────── */}
      <div className={`checkin-step-section${!claseSeleccionada ? ' step-disabled' : ''}`}>
        <p className="checkin-step-label">
          2 · Registra asistencia
          {claseSeleccionada && (
            <span className="checkin-step-clase"> — {claseSeleccionada.nombre} {claseSeleccionada.hora_inicio}</span>
          )}
        </p>

        <div className="checkin-asistencia-panel">
          {/* Cargando reservaciones */}
          {cargandoReservaciones && (
            <div className="checkin-fila"><span className="cargando" style={{ margin: 0 }}>Cargando reservaciones...</span></div>
          )}

          {/* Error cargando reservaciones */}
          {resultadosPorMiembro._error && (
            <div className="checkin-fila"><span style={{ color: 'var(--color-danger)', fontSize: '0.85rem' }}>✕ {resultadosPorMiembro._error}</span></div>
          )}

          {/* Filas de reservados */}
          {reservaciones.map(r => {
            const yaAsistio = asistencias.some(a => a.miembro_id === r.miembro_id && a.clase_id === claseSeleccionada.id)
            const res = resultadosPorMiembro[r.miembro_id]
            return (
              <div key={r.id} className={`checkin-fila${yaAsistio ? ' fila-ok' : ''}`}>
                <span className="checkin-fila-nombre">
                  {r.miembro ? `${r.miembro.nombre} ${r.miembro.apellido}` : `#${r.miembro_id}`}
                </span>
                <span className="checkin-fila-tag badge badge-inactivo">Reservado</span>
                {res?.ok === false && (
                  <span style={{ fontSize: '0.78rem', color: 'var(--color-danger)', flex: 1 }}>{res.mensaje}</span>
                )}
                {yaAsistio || res?.ok === true
                  ? <span className="badge badge-ok">✓ Presente</span>
                  : <button
                      className="btn btn-sm btn-primary"
                      onClick={() => registrarDirecto(r.miembro_id)}
                      disabled={cargando}
                    >Check-in</button>
                }
              </div>
            )
          })}

          {/* Separador walk-in */}
          <div className="checkin-fila checkin-fila-walkin">
            <div className="checkin-busqueda-wrap" style={{ flex: 1, position: 'relative' }}>
              <input
                ref={inputRef}
                className="input-busqueda"
                style={{ width: '100%' }}
                type="text"
                placeholder="Walk-in: buscar por nombre o apellido..."
                value={busqueda}
                disabled={!claseSeleccionada}
                onChange={e => { setBusqueda(e.target.value); setMiembro(null); setResultado(null) }}
                onKeyDown={e => e.key === 'Enter' && miembro && registrar()}
                autoComplete="off"
              />
              {sugerencias.length > 0 && (
                <ul className="checkin-sugerencias">
                  {sugerencias.map(m => (
                    <li key={m.id} onClick={() => seleccionar(m)}>
                      <strong>{m.nombre} {m.apellido}</strong>
                      {m.cedula && <span className="sug-detalle"> · {m.cedula}</span>}
                      {m.telefono && <span className="sug-detalle"> · {m.telefono}</span>}
                      {reservadoIds.has(m.id) && (
                        <span className="badge badge-ok" style={{ marginLeft: '0.5rem', fontSize: '0.72rem' }}>Ya reservó</span>
                      )}
                    </li>
                  ))}
                </ul>
              )}
              {buscando && <p className="cargando" style={{ margin: '0.25rem 0 0' }}>Buscando...</p>}
            </div>
            <button
              className="btn btn-primary btn-sm"
              onClick={registrar}
              disabled={!miembro || !claseSeleccionada || cargando}
            >
              {cargando ? '...' : 'Check-in'}
            </button>
          </div>

          {/* Feedback inline */}
          {(miembro && !resultado) && (
            <div className="checkin-fila" style={{ background: 'var(--color-surface-alt)' }}>
              <span className="checkin-fila-nombre">✓ {miembro.nombre} {miembro.apellido}</span>
              <button className="btn btn-sm btn-outline" onClick={limpiarMiembro}>Limpiar</button>
            </div>
          )}
          {resultado && (
            <div className={`checkin-resultado ${resultado.ok && !resultado.advertencia ? 'resultado-ok' : resultado.ok && resultado.advertencia ? 'resultado-warning' : 'resultado-error'}`}>
              {resultado.ok && !resultado.advertencia && '✓ '}
              {resultado.ok && resultado.advertencia && '⚠ '}
              {!resultado.ok && '✕ '}
              {resultado.mensaje}
              {resultado.advertencia && <div className="advertencia-detalle">{resultado.advertencia}</div>}
            </div>
          )}
        </div>
      </div>

      {/* ─── Log de asistencias ─────────────────────────────────────────────── */}
      <div className="page-header" style={{ marginTop: '2rem', flexWrap: 'wrap', gap: '0.75rem' }}>
        <h2 style={{ margin: 0, fontSize: '1rem', fontWeight: 600, color: 'var(--color-text-muted, #888)' }}>
          {esHoyLog ? 'Asistencias de hoy' : 'Asistencias'} ({asistencias.length})
        </h2>
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
          <input
            type="date"
            value={fechaDesde}
            max={fechaHasta}
            onChange={e => setFechaDesde(e.target.value)}
            style={{ fontSize: '0.82rem', padding: '0.3rem 0.5rem' }}
          />
          <span className="text-muted" style={{ fontSize: '0.82rem' }}>a</span>
          <input
            type="date"
            value={fechaHasta}
            min={fechaDesde}
            onChange={e => setFechaHasta(e.target.value)}
            style={{ fontSize: '0.82rem', padding: '0.3rem 0.5rem' }}
          />
          {!esHoyLog && (
            <button className="semana-hoy-btn" onClick={irAHoyLog}>Hoy</button>
          )}
        </div>
      </div>

      {cargandoLog ? (
        <p className="cargando">Cargando...</p>
      ) : errorLog ? (
        <p className="estado-msg error">{errorLog}</p>
      ) : asistencias.length === 0 ? (
        <p className="vacio">{esHoyLog ? 'Sin asistencias registradas hoy.' : 'Sin asistencias en el rango seleccionado.'}</p>
      ) : (
        <div className="tabla-wrapper">
          <table className="tabla">
            <thead>
              <tr>
                <th>Hora</th>
                <th>Clase</th>
                <th>Entrenador</th>
                <th>Miembro</th>
                <th>Notas</th>
              </tr>
            </thead>
            <tbody>
              {asistencias.map(a => (
                <tr key={a.id}>
                  <td>{formatFechaHora(a.fecha)}</td>
                  <td>{a.clase ? `${a.clase.nombre} ${a.clase.hora_inicio}` : '—'}</td>
                  <td>{a.clase?.entrenador || '—'}</td>
                  <td className="td-nombre">
                    {a.miembro ? `${a.miembro.nombre} ${a.miembro.apellido}` : `#${a.miembro_id}`}
                  </td>
                  <td>{a.notas || '—'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}
