import { useState, useEffect, useMemo } from 'react'
import { membresiasAPI, miembrosAPI, planesAPI, facturasAPI } from '../services/api'
import { formatFecha, parseFechaLocal, hoyLocal } from '@shared/utils/fecha'
import { useFocusTrap } from '@shared/hooks/useFocusTrap'
import '@shared/pages/Clientes.css'

const METODOS_PAGO = ['efectivo', 'transferencia', 'tarjeta']

const ESTADOS_FILTRO = [
  { value: 'activos',  label: 'Activos'  },
  { value: 'todos',    label: 'Todos'    },
  { value: 'vencidas', label: 'Vencidas' },
]

const BADGE = {
  activa:          'badge-ok',
  por_vencer:      'badge-warning',
  critica:         'badge-danger',
  pendiente_pago:  'badge-warning',
  vencida:         'badge-inactivo',
  cancelada:       'badge-inactivo',
}

const LABEL = {
  activa:          'Al día',
  por_vencer:      'Por vencer',
  critica:         'Crítica',
  pendiente_pago:  'Con deuda',
  vencida:         'Vencida',
  cancelada:       'Cancelada',
}

const ESTADOS_VIGENTES = new Set(['activa', 'por_vencer', 'critica', 'pendiente_pago'])
const PRIORIDAD = { critica: 0, pendiente_pago: 1, por_vencer: 2, activa: 3, vencida: 4, cancelada: 5 }

function dotColor(activas) {
  if (!activas.length) return '#cbd5e1'
  const estados = activas.map(m => m.estado)
  if (estados.some(e => e === 'critica'))    return '#ef4444'
  if (estados.some(e => e === 'por_vencer')) return '#f59e0b'
  return '#22c55e'
}

function rowClass(estado) {
  if (estado === 'critica')    return 'tr-critica'
  if (estado === 'por_vencer') return 'tr-warning'
  if (estado === 'vencida')    return 'tr-vencida'
  return ''
}

function venceDisplay(m) {
  if (m.clases_total !== null && m.clases_total !== undefined) {
    const r = Math.max(0, m.clases_total - (m.clases_usadas ?? 0))
    return `${r} clase${r !== 1 ? 's' : ''}`
  }
  if (!m.fecha_fin) return '—'
  // Medianoche contra medianoche, no contra la hora actual — mismo cálculo
  // que el backend ((fecha_fin - hoy).days en membresias.py): comparar contra
  // new Date() (con hora) hacía aparecer "Vencida" horas antes de medianoche.
  const dias = Math.round((parseFechaLocal(m.fecha_fin) - parseFechaLocal(hoyLocal())) / 86400000)
  if (dias < 0)   return 'Vencida'
  if (dias === 0) return 'Hoy'
  if (dias === 1) return '1 día'
  return `${dias} días`
}


export default function Membresias({ rol }) {
  const [todas,      setTodas]      = useState([])
  const [cargando,   setCargando]   = useState(true)
  const [error,      setError]      = useState(null)
  const [planActivo, setPlanActivo] = useState(null)
  const [filtroEst,  setFiltroEst]  = useState('activos')

  const [modal,     setModal]     = useState(null)
  const [renovarId, setRenovarId] = useState(null)
  const [guardando, setGuardando] = useState(false)
  const [eliminarModal, setEliminarModal] = useState(null)  // { id, nombre }
  const [eliminando,    setEliminando]    = useState(false)
  const [eliminarError, setEliminarError] = useState(null)

  const [asistModal, setAsistModal] = useState(null)  // { id, nombre }
  const [asistValor, setAsistValor] = useState('')
  const [guardandoAsist, setGuardandoAsist] = useState(false)
  const [asistError,     setAsistError]     = useState(null)
  const [miembros,  setMiembros]  = useState([])
  const [planes,    setPlanes]    = useState([])
  const [form,      setForm]      = useState({
    miembro_id: '', plan_id: '', fecha_inicio: '', precio_pagado: '', metodo_pago: 'efectivo', notas: '', comprobante: null,
  })

  const modalRef = useFocusTrap(!!modal)
  const eliminarModalRef = useFocusTrap(!!eliminarModal)
  const asistModalRef    = useFocusTrap(!!asistModal)

  // ─── Carga ───────────────────────────────────────────────────────────────────

  async function cargar() {
    try {
      setCargando(true)
      setError(null)
      const res = await membresiasAPI.listar()
      setTodas(res.data)
    } catch {
      setError('No se pudo conectar con el servidor.')
    } finally {
      setCargando(false)
    }
  }

  useEffect(() => { cargar() }, [])

  // ─── Agrupación por plan ──────────────────────────────────────────────────────

  const grupos = useMemo(() => {
    const map = new Map()
    todas.forEach(m => {
      if (!map.has(m.plan_id)) {
        map.set(m.plan_id, {
          plan_id:     m.plan_id,
          plan_nombre: m.plan?.nombre ?? `Plan #${m.plan_id}`,
          plan_tipo:   m.plan?.tipo   ?? '',
          plan_precio: m.plan?.precio ?? 0,
          membresias:  [],
        })
      }
      map.get(m.plan_id).membresias.push(m)
    })
    return [...map.values()].sort((a, b) => {
      const worst = g => Math.min(...g.membresias.map(m => PRIORIDAD[m.estado] ?? 5))
      return worst(a) - worst(b)
    })
  }, [todas])

  useEffect(() => {
    if (planActivo === null && grupos.length > 0)
      setPlanActivo(grupos[0].plan_id)
  }, [grupos])

  const grupoActivo = grupos.find(g => g.plan_id === planActivo) ?? null

  const membresiasFiltradas = useMemo(() => {
    if (!grupoActivo) return []
    const ms = grupoActivo.membresias
    if (filtroEst === 'activos')  return ms.filter(m => ESTADOS_VIGENTES.has(m.estado))
    if (filtroEst === 'vencidas') return ms.filter(m => !ESTADOS_VIGENTES.has(m.estado))
    return ms
  }, [grupoActivo, filtroEst])

  // ─── Modal ───────────────────────────────────────────────────────────────────

  async function abrirNueva() {
    try {
      const [mRes, pRes] = await Promise.all([
        miembrosAPI.listar({ activo: true }),
        planesAPI.listar(),
      ])
      setMiembros(mRes.data)
      setPlanes(pRes.data)
      const planObj = pRes.data.find(p => p.id === planActivo)
      setForm({
        miembro_id: '',
        plan_id:    planActivo ? String(planActivo) : '',
        fecha_inicio:  hoyLocal(),
        precio_pagado: planObj?.precio ?? '',
        metodo_pago:   'efectivo',
        notas:         '',
        comprobante:   null,
      })
      setRenovarId(null)
      setModal('nueva')
    } catch {
      alert('No se pudieron cargar los datos.')
    }
  }

  async function abrirRenovar(m) {
    try {
      const pRes = await planesAPI.listar()
      setPlanes(pRes.data)
      setForm({ plan_id: String(m.plan_id), fecha_inicio: hoyLocal(), precio_pagado: m.plan?.precio ?? '', metodo_pago: 'efectivo', notas: '', comprobante: null })
      setRenovarId(m.id)
      setModal('renovar')
    } catch {
      alert('No se pudieron cargar los planes.')
    }
  }

  function cerrarModal() { setModal(null); setRenovarId(null) }

  function abrirEliminar(m) {
    setEliminarError(null)
    setEliminarModal({
      id:     m.id,
      nombre: m.miembro ? `${m.miembro.nombre} ${m.miembro.apellido}` : `#${m.miembro_id}`,
    })
  }

  async function confirmarEliminar() {
    if (!eliminarModal) return
    try {
      setEliminando(true)
      setEliminarError(null)
      await membresiasAPI.eliminar(eliminarModal.id)
      setEliminarModal(null)
      cargar()
    } catch (err) {
      setEliminarError(err.response?.data?.detail ?? 'No se pudo eliminar la membresía.')
    } finally {
      setEliminando(false)
    }
  }

  function abrirAsistencias(m) {
    setAsistError(null)
    setAsistValor(String(m.clases_usadas ?? 0))
    setAsistModal({
      id:     m.id,
      nombre: m.miembro ? `${m.miembro.nombre} ${m.miembro.apellido}` : `#${m.miembro_id}`,
    })
  }

  async function guardarAsistencias(e) {
    e.preventDefault()
    const valor = parseInt(asistValor, 10)
    if (isNaN(valor) || valor < 0 || valor > 90) {
      setAsistError('Ingresa un número entre 0 y 90.')
      return
    }
    try {
      setGuardandoAsist(true)
      setAsistError(null)
      await membresiasAPI.editarAsistencias(asistModal.id, valor)
      setAsistModal(null)
      cargar()
    } catch (err) {
      setAsistError(err.response?.data?.detail ?? 'No se pudo guardar.')
    } finally {
      setGuardandoAsist(false)
    }
  }

  function handleChange(e) {
    const { name, value } = e.target
    setForm(prev => {
      const next = { ...prev, [name]: value }
      if (name === 'plan_id' && value) {
        const p = planes.find(p => p.id === Number(value))
        if (p) next.precio_pagado = p.precio
      }
      return next
    })
  }

  function handleArchivo(e) {
    setForm(prev => ({ ...prev, comprobante: e.target.files[0] || null }))
  }

  async function guardar(e) {
    e.preventDefault()
    if (!form.plan_id)       return alert('Selecciona un plan.')
    if (!form.fecha_inicio)  return alert('La fecha de inicio es obligatoria.')
    if (!form.precio_pagado) return alert('El precio pagado es obligatorio.')

    const base = {
      plan_id:       parseInt(form.plan_id),
      fecha_inicio:  form.fecha_inicio,
      precio_pagado: parseFloat(form.precio_pagado),
      metodo_pago:   form.metodo_pago,
      notas:         form.notas || null,
      comprobante:   form.comprobante,
    }

    try {
      setGuardando(true)
      if (modal === 'nueva') {
        if (!form.miembro_id) return alert('Selecciona un miembro.')
        await membresiasAPI.crear({ ...base, miembro_id: parseInt(form.miembro_id) })
      } else {
        await membresiasAPI.renovar(renovarId, base)
      }
      cerrarModal()
      cargar()
    } catch (err) {
      alert(err.response?.data?.detail ?? 'Error al guardar.')
    } finally {
      setGuardando(false)
    }
  }

  // ─── Saldo dinámico del modal ────────────────────────────────────────────────

  const _planModal    = form.plan_id ? planes.find(p => p.id === Number(form.plan_id)) : null
  const _totalModal   = _planModal?.precio ?? 0
  const _saldoModal   = _totalModal > 0
    ? Math.max(0, _totalModal - (parseFloat(form.precio_pagado) || 0))
    : 0

  // ─── Render ──────────────────────────────────────────────────────────────────

  return (
    <div className="page clientes">
      <div className="page-header">
        <h1>Membresías</h1>
        <button className="btn btn-primary" onClick={abrirNueva}>+ Añadir miembro</button>
      </div>

      {error && <p className="mensaje-error">{error}</p>}

      {cargando ? (
        <p className="cargando">Cargando...</p>
      ) : grupos.length === 0 ? (
        <p className="vacio">No hay membresías registradas.</p>
      ) : (
        <div className="membresias-layout">

          {/* ── Sidebar de planes ─────────────────────────────── */}
          <aside className="plan-nav">
            <div className="plan-nav-header">Planes</div>
            {grupos.map(g => {
              const activas = g.membresias.filter(m => ESTADOS_VIGENTES.has(m.estado))
              return (
                <button
                  key={g.plan_id}
                  className={`plan-nav-item ${planActivo === g.plan_id ? 'activo' : ''}`}
                  onClick={() => setPlanActivo(g.plan_id)}
                >
                  <span className="plan-dot" style={{ background: dotColor(activas) }} />
                  <span className="plan-nav-nombre">{g.plan_nombre}</span>
                  <span className="plan-nav-count">{activas.length}</span>
                </button>
              )
            })}
          </aside>

          {/* ── Contenido del plan seleccionado ───────────────── */}
          <div className="plan-contenido">
            {!grupoActivo ? (
              <p className="plan-empty">Selecciona un plan.</p>
            ) : (
              <>
                <div className="plan-header">
                  <h2>{grupoActivo.plan_nombre}</h2>
                  <span className={`badge ${grupoActivo.plan_tipo === 'tiempo' ? 'badge-ok' : 'badge-warning'}`}>
                    {grupoActivo.plan_tipo === 'tiempo' ? 'Por tiempo' : 'Por clases'}
                  </span>
                  <span className="plan-precio">${parseFloat(grupoActivo.plan_precio).toFixed(2)}</span>
                </div>

                <div className="plan-toolbar">
                  {ESTADOS_FILTRO.map(f => (
                    <button
                      key={f.value}
                      className={`btn-filtro ${filtroEst === f.value ? 'activo' : ''}`}
                      onClick={() => setFiltroEst(f.value)}
                    >
                      {f.label}
                    </button>
                  ))}
                  <span className="total-label">
                    {membresiasFiltradas.length} membresía{membresiasFiltradas.length !== 1 ? 's' : ''}
                  </span>
                </div>

                {membresiasFiltradas.length === 0 ? (
                  <p className="plan-empty">Sin membresías para este filtro.</p>
                ) : (
                  <div className="tabla-wrapper" style={{ border: 'none', borderRadius: 0 }}>
                    <table className="tabla">
                      <thead>
                        <tr>
                          <th>Miembro</th>
                          <th>Inicio</th>
                          <th>Vence / Clases</th>
                          {grupoActivo.plan_tipo !== 'tiempo' && <th>Asistidas</th>}
                          <th>Pagado</th>
                          <th>Estado</th>
                          <th>Acciones</th>
                        </tr>
                      </thead>
                      <tbody>
                        {membresiasFiltradas.map(m => (
                          <tr key={m.id} className={rowClass(m.estado)}>
                            <td className="td-nombre">
                              {m.miembro
                                ? `${m.miembro.nombre} ${m.miembro.apellido}`
                                : `#${m.miembro_id}`}
                            </td>
                            <td>{formatFecha(m.fecha_inicio)}</td>
                            <td className="num">{venceDisplay(m)}</td>
                            {grupoActivo.plan_tipo !== 'tiempo' && (
                              <td className="num">
                                {rol === 'admin' ? (
                                  <button
                                    className="btn-link-num"
                                    onClick={() => abrirAsistencias(m)}
                                    title="Editar sesiones asistidas"
                                  >
                                    {m.clases_usadas ?? 0}
                                  </button>
                                ) : (
                                  m.clases_usadas ?? 0
                                )}
                              </td>
                            )}
                            <td className="num">${parseFloat(m.precio_pagado).toFixed(2)}</td>
                            <td>
                              <span className={`badge ${BADGE[m.estado] ?? 'badge-inactivo'}`}>
                                {LABEL[m.estado] ?? m.estado}
                              </span>
                            </td>
                            <td className="td-acciones">
                              {m.estado !== 'cancelada' && (
                                <button
                                  className="btn btn-sm btn-outline"
                                  onClick={() => abrirRenovar(m)}
                                >
                                  Renovar
                                </button>
                              )}
                              <a
                                className="btn btn-sm btn-outline"
                                href={facturasAPI.membresiaPdf(m.id)}
                                target="_blank" rel="noreferrer"
                              >
                                Factura
                              </a>
                              <button
                                className="btn btn-sm btn-danger"
                                onClick={() => abrirEliminar(m)}
                                title="Corregir un registro mal cargado"
                              >
                                Eliminar
                              </button>
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}
              </>
            )}
          </div>
        </div>
      )}

      {/* ── Modal nueva / renovar ─────────────────────────────────────────────── */}
      {modal && (
        <div className="modal-overlay" onClick={cerrarModal}>
          <div className="modal" ref={modalRef} tabIndex={-1} onClick={e => e.stopPropagation()}>
            <div className="modal-header">
              <h2>{modal === 'nueva' ? 'Nueva membresía' : 'Renovar membresía'}</h2>
              <button className="modal-close" onClick={cerrarModal}>✕</button>
            </div>
            <form className="modal-form" onSubmit={guardar}>
              {modal === 'nueva' && (
                <label>
                  <span className="label-text">Miembro <span className="required">*</span></span>
                  <select name="miembro_id" value={form.miembro_id} onChange={handleChange} required>
                    <option value="">— Seleccionar miembro —</option>
                    {(() => {
                      const conMembresia = new Set(todas.filter(mem => ESTADOS_VIGENTES.has(mem.estado)).map(mem => mem.miembro_id))
                      return miembros
                        .filter(m => !conMembresia.has(m.id))
                        .map(m => (
                          <option key={m.id} value={m.id}>{m.nombre} {m.apellido}</option>
                        ))
                    })()}
                  </select>
                </label>
              )}

              <label>
                <span className="label-text">Plan <span className="required">*</span></span>
                <select name="plan_id" value={form.plan_id} onChange={handleChange} required>
                  <option value="">— Seleccionar plan —</option>
                  {planes.map(p => (
                    <option key={p.id} value={p.id}>
                      {p.nombre} — ${parseFloat(p.precio).toFixed(2)}
                      {p.tipo === 'tiempo' ? ` (${p.duracion_dias}d)` : ` (${p.clases_total} clases)`}
                    </option>
                  ))}
                </select>
              </label>

              <div className="form-row">
                <label>
                  <span className="label-text">Fecha inicio <span className="required">*</span></span>
                  <input name="fecha_inicio" type="date" value={form.fecha_inicio} onChange={handleChange} required />
                </label>
                <label>
                  <span className="label-text">
                    Pago inicial <span className="required">*</span>
                    {_totalModal > 0 && (
                      <span className="label-hint">de ${_totalModal.toFixed(2)}</span>
                    )}
                  </span>
                  <input name="precio_pagado" type="number" step="0.01" min="0" max={_totalModal || undefined} value={form.precio_pagado} onChange={handleChange} placeholder="0.00" required />
                </label>
              </div>

              {_totalModal > 0 && form.precio_pagado !== '' && (
                <div className={`saldo-modal-preview ${_saldoModal > 0 ? 'saldo-pendiente' : 'saldo-completo'}`}>
                  {_saldoModal > 0
                    ? `Quedará un saldo pendiente de $${_saldoModal.toFixed(2)}`
                    : '✓ Pago completo'}
                </div>
              )}

              <label>
                <span className="label-text">Método de pago <span className="required">*</span></span>
                <select name="metodo_pago" value={form.metodo_pago} onChange={handleChange}>
                  {METODOS_PAGO.map(m => <option key={m} value={m}>{m}</option>)}
                </select>
              </label>

              <label>
                <span className="label-text">Notas</span>
                <input name="notas" value={form.notas} onChange={handleChange} />
              </label>

              <label>
                <span className="label-text">
                  Comprobante de pago
                  <span className="label-hint">opcional · jpg o png</span>
                </span>
                <input type="file" accept="image/jpeg,image/png" onChange={handleArchivo} />
              </label>

              <div className="modal-footer">
                <button type="button" className="btn btn-outline" onClick={cerrarModal}>Cancelar</button>
                <button type="submit" className="btn btn-primary" disabled={guardando}>
                  {guardando ? 'Guardando...' : 'Guardar'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* ── Modal confirmar eliminación ────────────────────────────────────── */}
      {eliminarModal && (
        <div className="modal-overlay" onClick={() => !eliminando && setEliminarModal(null)}>
          <div className="modal" ref={eliminarModalRef} tabIndex={-1} onClick={e => e.stopPropagation()}>
            <div className="modal-header">
              <h2>¿Eliminar esta membresía?</h2>
              <button className="modal-close" onClick={() => setEliminarModal(null)} disabled={eliminando}>✕</button>
            </div>
            <p style={{ padding: '0 1.5rem' }}>
              <strong>{eliminarModal.nombre}</strong> — esta acción no se puede deshacer.
              Usala solo para corregir un registro mal cargado (plan equivocado, miembro
              equivocado, etc.), no para cancelar una membresía real.
            </p>
            {eliminarError && <p className="mensaje-error" style={{ margin: '0 1.5rem' }}>{eliminarError}</p>}
            <div className="modal-footer">
              <button className="btn btn-outline" onClick={() => setEliminarModal(null)} disabled={eliminando}>
                Cancelar
              </button>
              <button className="btn btn-danger" onClick={confirmarEliminar} disabled={eliminando}>
                {eliminando ? 'Eliminando...' : 'Sí, eliminar'}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ── Modal editar asistencias ──────────────────────────────────────── */}
      {asistModal && (
        <div className="modal-overlay" onClick={() => !guardandoAsist && setAsistModal(null)}>
          <div className="modal" ref={asistModalRef} tabIndex={-1} onClick={e => e.stopPropagation()}>
            <div className="modal-header">
              <h2>Editar sesiones asistidas</h2>
              <button className="modal-close" onClick={() => setAsistModal(null)} disabled={guardandoAsist}>✕</button>
            </div>
            <form className="modal-form" onSubmit={guardarAsistencias}>
              <p style={{ margin: '0 0 0.5rem' }}>
                <strong>{asistModal.nombre}</strong> — usalo para dejar constancia de
                sesiones hechas antes de usar el sistema, o para corregir el conteo.
              </p>
              <label>
                <span className="label-text">Sesiones asistidas <span className="required">*</span></span>
                <input
                  type="number" min="0" max="90" step="1"
                  value={asistValor}
                  onChange={e => setAsistValor(e.target.value)}
                  autoFocus required
                />
              </label>
              {asistError && <p className="mensaje-error">{asistError}</p>}
              <div className="modal-footer">
                <button type="button" className="btn btn-outline" onClick={() => setAsistModal(null)} disabled={guardandoAsist}>
                  Cancelar
                </button>
                <button type="submit" className="btn btn-primary" disabled={guardandoAsist}>
                  {guardandoAsist ? 'Guardando...' : 'Guardar'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  )
}
