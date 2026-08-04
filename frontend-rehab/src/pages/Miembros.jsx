import { useState, useEffect, useCallback, useMemo, useRef } from 'react'
import { useLocation } from 'react-router-dom'
import { miembrosAPI, membresiasAPI, facturasAPI, historialMedicoAPI } from '../services/api'
import { formatFecha, formatFechaHora, hoyLocal, parseFechaLocal } from '@shared/utils/fecha'
import { fmtMetodoPago, estadoMembresiaBadge } from '@shared/utils/formato'
import { useFocusTrap } from '@shared/hooks/useFocusTrap'
import '@shared/pages/Clientes.css'

const TIPO_HISTORIAL = {
  patologia:        'Patología',
  lesion_previa:    'Lesión previa',
  operacion_previa: 'Operación previa',
}

const NUEVO_REGISTRO_VACIO = { tipo: 'patologia', descripcion: '', fecha: '', activa: true, notas: '' }

const FORM_VACIO = {
  nombre:              '',
  apellido:            '',
  fecha_ingreso:       '',
  email:               '',
  telefono:            '',
  cedula:              '',
  fecha_nacimiento:    '',
  contacto_emergencia: '',
  peso:                '',
  altura:              '',
  notas:               '',
}

function calcularEdad(fechaNacimiento) {
  if (!fechaNacimiento) return null
  const nacimiento = parseFechaLocal(fechaNacimiento)
  const hoy = new Date()
  let edad = hoy.getFullYear() - nacimiento.getFullYear()
  const mesActual = hoy.getMonth() - nacimiento.getMonth()
  if (mesActual < 0 || (mesActual === 0 && hoy.getDate() < nacimiento.getDate())) edad--
  return edad
}

function calcularIMC(peso, altura) {
  if (!peso || !altura) return null
  const alturaM = altura / 100
  return peso / (alturaM * alturaM)
}

function categoriaIMC(imc) {
  if (imc == null) return null
  if (imc < 18.5) return 'Bajo peso'
  if (imc < 25)   return 'Normal'
  if (imc < 30)   return 'Sobrepeso'
  return 'Obesidad'
}

const FILTROS = [
  { value: 'todos',      label: 'Todos'      },
  { value: 'nuevos',     label: 'Nuevos este mes' },
  { value: 'al_dia',     label: 'Al día'     },
  { value: 'por_vencer', label: 'Por vencer' },
  { value: 'critica',    label: 'Crítica'    },
  { value: 'vencida',    label: 'Vencida'    },
  { value: 'sin_plan',   label: 'Sin plan'   },
  { value: 'inactivos',  label: 'Inactivos'  },
]

// Compara por prefijo "YYYY-MM" en vez de parsear con Date: fecha_ingreso
// llega como string plano "YYYY-MM-DD" del backend, y construir un Date a
// partir de eso interpreta medianoche UTC — con timezones negativos corre la
// fecha un día para atrás (mismo problema que ya está documentado en
// utils/fecha.js). Comparar el string evita ese bug por completo.
//
// mesFiltro es "YYYY-MM" y no el mes calendario real: cuando se llega acá
// desde la tarjeta "Nuevos este mes" del Dashboard estando en un mes pasado,
// el filtro tiene que mostrar los nuevos de ESE mes, no del mes real de hoy
// — si no, el número que el usuario acaba de ver en el KPI no coincide con
// lo que encuentra al hacer clic.
function esNuevoDelMes(m, mesFiltro) {
  return m.fecha_ingreso.slice(0, 7) === mesFiltro
}

// Única fuente de verdad para "¿este miembro pertenece a este filtro?" —
// la usan tanto la lista filtrada como el conteo de cada pill, así ambos
// no pueden desincronizarse entre sí.
function perteneceAFiltro(m, value, mesFiltro) {
  if (value === 'inactivos') return !m.activo
  if (!m.activo)             return false
  const estado = m.membresia_activa?.estado
  if (value === 'todos')      return true
  if (value === 'nuevos')     return esNuevoDelMes(m, mesFiltro)
  if (value === 'al_dia')     return estado === 'activa'
  if (value === 'por_vencer') return estado === 'por_vencer'
  if (value === 'critica')    return estado === 'critica'
  if (value === 'vencida')    return estado === 'vencida'
  if (value === 'sin_plan')   return !m.membresia_activa
  return false
}

function estadoBadge(m) {
  if (!m.activo) return { label: 'Inactivo',   clase: 'badge-inactivo' }
  const ma = m.membresia_activa
  if (!ma)                          return { label: 'Sin plan',   clase: 'badge-sin-plan' }
  if (ma.estado === 'activa')       return { label: 'Al día',     clase: 'badge-ok'       }
  if (ma.estado === 'por_vencer')   return { label: 'Por vencer', clase: 'badge-warning'  }
  if (ma.estado === 'critica')      return { label: 'Crítica',    clase: 'badge-danger'   }
  if (ma.estado === 'vencida')      return { label: 'Vencida',    clase: 'badge-inactivo' }
  return { label: ma.estado, clase: 'badge-inactivo' }
}

function rowClass(m) {
  if (!m.activo) return 'tr-inactivo'
  const e = m.membresia_activa?.estado
  if (e === 'critica')    return 'tr-critica'
  if (e === 'por_vencer') return 'tr-warning'
  if (e === 'vencida')    return 'tr-vencida'
  if (!m.membresia_activa) return 'tr-sin-plan'
  return ''
}

function venceDisplay(m) {
  const ma = m.membresia_activa
  if (!ma) return '—'
  if (ma.clases_restantes !== null && ma.clases_restantes !== undefined)
    return `${ma.clases_restantes} clase${ma.clases_restantes !== 1 ? 's' : ''}`
  if (ma.dias_restantes !== null && ma.dias_restantes !== undefined) {
    if (ma.dias_restantes === 0) return 'Hoy'
    if (ma.dias_restantes === 1) return '1 día'
    return `${ma.dias_restantes} días`
  }
  return '—'
}


export default function Miembros() {
  const location = useLocation()

  const [miembros,   setMiembros]   = useState([])
  const [busqueda,   setBusqueda]   = useState('')
  // Llega con filtro preseleccionado cuando se navega acá desde la tarjeta
  // "Nuevos este mes" del Dashboard — navigate('/miembros', { state: { filtro, mes, anio } }).
  const [filtro,     setFiltro]     = useState(location.state?.filtro ?? 'todos')
  // "YYYY-MM" del mes que se estaba viendo en el Dashboard al navegar acá —
  // si no viene (entrada directa a la página), es el mes real de hoy.
  const [mesFiltro] = useState(
    location.state?.mes && location.state?.anio
      ? `${location.state.anio}-${String(location.state.mes).padStart(2, '0')}`
      : hoyLocal().slice(0, 7)
  )
  const [cargando,   setCargando]   = useState(true)
  const [error,      setError]      = useState(null)
  const [modal,      setModal]      = useState(null)
  const [form,       setForm]       = useState(FORM_VACIO)
  const [editandoId, setEditandoId] = useState(null)
  const [guardando,  setGuardando]  = useState(false)
  const [histModal,   setHistModal]   = useState(null) // { miembro, cargando, error, membresias: [{...membresia, pagos}] }
  const [perfilModal, setPerfilModal] = useState(null) // { miembro, cargando, error, historial: [] }
  const [nuevoRegistro,     setNuevoRegistro]     = useState(NUEVO_REGISTRO_VACIO)
  const [mostrarFormFicha,  setMostrarFormFicha]  = useState(false)
  const [guardandoRegistro, setGuardandoRegistro] = useState(false)

  const modalRef       = useFocusTrap(!!modal)
  const histModalRef   = useFocusTrap(!!histModal)
  const perfilModalRef = useFocusTrap(!!perfilModal)

  // ─── Carga ──────────────────────────────────────────────────────────────────

  const cargar = useCallback(async (q = busqueda) => {
    try {
      setCargando(true)
      setError(null)
      const params = {}
      if (q) params.q = q
      const res = await miembrosAPI.listar(params)
      setMiembros(res.data)
    } catch {
      setError('No se pudo conectar con el servidor.')
    } finally {
      setCargando(false)
    }
  }, [busqueda])

  useEffect(() => { cargar('') }, [])

  // El montaje ya dispara la carga de arriba — sin este guard, este efecto
  // también corre en el montaje (todo efecto corre al montar sin importar
  // sus dependencias) y programa una segunda carga idéntica 300ms después.
  const primeraCargaDebounce = useRef(true)
  useEffect(() => {
    if (primeraCargaDebounce.current) { primeraCargaDebounce.current = false; return }
    const t = setTimeout(() => cargar(busqueda), 300)
    return () => clearTimeout(t)
  }, [busqueda])

  // ─── Filtro local ───────────────────────────────────────────────────────────
  // Memoizados: sin esto, escanean miembros × 8 filtros en cada render, incluso
  // los que no tienen nada que ver con miembros (ej. tipear en otro campo).

  const filtrados = useMemo(
    () => miembros.filter(m => perteneceAFiltro(m, filtro, mesFiltro)),
    [miembros, filtro, mesFiltro]
  )

  // ─── Conteos para badges en filtros ─────────────────────────────────────────

  const conteos = useMemo(() => {
    const c = Object.fromEntries(FILTROS.map(f => [f.value, 0]))
    for (const m of miembros) {
      for (const f of FILTROS) {
        if (perteneceAFiltro(m, f.value, mesFiltro)) c[f.value]++
      }
    }
    return c
  }, [miembros, mesFiltro])

  // ─── Modal ──────────────────────────────────────────────────────────────────

  function abrirCrear() {
    setForm(FORM_VACIO)
    setEditandoId(null)
    setModal('crear')
  }

  function abrirEditar(m) {
    setForm({
      nombre:              m.nombre              ?? '',
      apellido:            m.apellido            ?? '',
      fecha_ingreso:       m.fecha_ingreso        ?? '',
      email:               m.email               ?? '',
      telefono:            m.telefono            ?? '',
      cedula:              m.cedula              ?? '',
      fecha_nacimiento:    m.fecha_nacimiento    ?? '',
      contacto_emergencia: m.contacto_emergencia ?? '',
      peso:                m.peso                ?? '',
      altura:              m.altura              ?? '',
      notas:               m.notas               ?? '',
    })
    setEditandoId(m.id)
    setModal('editar')
  }

  function cerrarModal() {
    setModal(null)
    setForm(FORM_VACIO)
    setEditandoId(null)
  }

  function handleChange(e) {
    const { name, value } = e.target
    setForm(prev => ({ ...prev, [name]: value }))
  }

  // ─── Guardar ────────────────────────────────────────────────────────────────

  async function guardar(e) {
    e.preventDefault()
    if (!form.nombre.trim())    return alert('El nombre es obligatorio.')
    if (!form.apellido.trim())  return alert('El apellido es obligatorio.')
    if (!form.fecha_ingreso)    return alert('La fecha de ingreso es obligatoria.')

    const payload = {
      nombre:              form.nombre.trim(),
      apellido:            form.apellido.trim(),
      fecha_ingreso:       form.fecha_ingreso,
      email:               form.email.trim()               || null,
      telefono:            form.telefono.trim()             || null,
      cedula:              form.cedula.trim()               || null,
      fecha_nacimiento:    form.fecha_nacimiento            || null,
      contacto_emergencia: form.contacto_emergencia.trim()  || null,
      peso:                form.peso   !== '' ? Number(form.peso)   : null,
      altura:              form.altura !== '' ? Number(form.altura) : null,
      notas:               form.notas.trim()                || null,
    }

    try {
      setGuardando(true)
      if (modal === 'crear') {
        await miembrosAPI.crear(payload)
      } else {
        await miembrosAPI.actualizar(editandoId, payload)
      }
      cerrarModal()
      cargar(busqueda)
    } catch (err) {
      alert(err.response?.data?.detail ?? 'Error al guardar.')
    } finally {
      setGuardando(false)
    }
  }

  // ─── Desactivar / Reactivar ──────────────────────────────────────────────────

  async function desactivar(m) {
    if (!confirm(`¿Desactivar a "${m.nombre} ${m.apellido}"?`)) return
    try {
      await miembrosAPI.desactivar(m.id)
      cargar(busqueda)
    } catch (err) {
      alert(err.response?.data?.detail ?? 'No se pudo desactivar el paciente.')
    }
  }

  async function reactivar(m) {
    if (!confirm(`¿Reactivar a "${m.nombre} ${m.apellido}"?`)) return
    try {
      await miembrosAPI.reactivar(m.id)
      cargar(busqueda)
    } catch (err) {
      alert(err.response?.data?.detail ?? 'No se pudo reactivar el paciente.')
    }
  }

  // ─── Historial de pagos ─────────────────────────────────────────────────────

  async function abrirHistorial(m) {
    setHistModal({ miembro: m, cargando: true, error: null, membresias: [] })
    try {
      const res = await membresiasAPI.historialMiembro(m.id)
      setHistModal(prev => ({ ...prev, cargando: false, membresias: res.data }))
    } catch {
      setHistModal(prev => ({ ...prev, cargando: false, error: 'No se pudo cargar el historial.' }))
    }
  }

  function cerrarHistorial() {
    setHistModal(null)
  }

  // ─── Perfil (identidad + biometría + membresía + historial médico) ─────────

  async function abrirPerfil(m) {
    setPerfilModal({ miembro: m, cargando: true, error: null, historial: [] })
    setNuevoRegistro(NUEVO_REGISTRO_VACIO)
    setMostrarFormFicha(false)
    try {
      const res = await historialMedicoAPI.listarPaciente(m.id)
      setPerfilModal(prev => ({ ...prev, cargando: false, historial: res.data }))
    } catch {
      setPerfilModal(prev => ({ ...prev, cargando: false, error: 'No se pudo cargar la ficha médica.' }))
    }
  }

  function cerrarPerfil() {
    setPerfilModal(null)
  }

  async function agregarRegistro(e) {
    e.preventDefault()
    if (!nuevoRegistro.descripcion.trim()) return alert('La descripción es obligatoria.')
    try {
      setGuardandoRegistro(true)
      await historialMedicoAPI.crear({
        paciente_id: perfilModal.miembro.id,
        tipo:        nuevoRegistro.tipo,
        descripcion: nuevoRegistro.descripcion.trim(),
        fecha:       nuevoRegistro.fecha || null,
        activa:      nuevoRegistro.activa,
        notas:       nuevoRegistro.notas.trim() || null,
      })
      const res = await historialMedicoAPI.listarPaciente(perfilModal.miembro.id)
      setPerfilModal(prev => ({ ...prev, historial: res.data }))
      setNuevoRegistro(NUEVO_REGISTRO_VACIO)
      setMostrarFormFicha(false)
    } catch (err) {
      alert(err.response?.data?.detail ?? 'No se pudo guardar el registro.')
    } finally {
      setGuardandoRegistro(false)
    }
  }

  async function eliminarRegistro(id) {
    if (!confirm('¿Eliminar este registro definitivamente? Esta acción no se puede deshacer.')) return
    try {
      await historialMedicoAPI.eliminar(id)
      setPerfilModal(prev => ({ ...prev, historial: prev.historial.filter(r => r.id !== id) }))
    } catch (err) {
      // 403 = solo quien lo creó puede eliminarlo — el backend ya explica esto,
      // se lo mostramos tal cual (mismo criterio que eliminar_instructor).
      alert(err.response?.data?.detail ?? 'No se pudo eliminar el registro.')
    }
  }

  // ─── Render ─────────────────────────────────────────────────────────────────

  return (
    <div className="page clientes">
      <div className="page-header">
        <h1>Pacientes</h1>
        <button className="btn btn-primary" onClick={abrirCrear}>+ Nuevo paciente</button>
      </div>

      <div className="toolbar">
        <input
          className="input-busqueda"
          type="text"
          placeholder="Buscar por nombre, apellido o cédula..."
          value={busqueda}
          onChange={e => setBusqueda(e.target.value)}
        />
        <div className="filtros">
          {FILTROS.map(f => {
            const n = conteos[f.value]
            return (
              <button
                key={f.value}
                className={`btn-filtro ${filtro === f.value ? 'activo' : ''}`}
                onClick={() => setFiltro(f.value)}
              >
                {f.label}
                {n > 0 && <span style={{ marginLeft: '0.3rem', opacity: 0.7 }}>({n})</span>}
              </button>
            )
          })}
        </div>
        <span className="total-label">{filtrados.length} paciente{filtrados.length !== 1 ? 's' : ''}</span>
      </div>

      {error && <p className="mensaje-error">{error}</p>}

      {cargando ? (
        <p className="cargando">Cargando...</p>
      ) : filtrados.length === 0 ? (
        <p className="vacio">
          {busqueda ? 'Sin resultados.' : 'No hay pacientes en este filtro.'}
        </p>
      ) : (
        <div className="tabla-wrapper">
          <table className="tabla">
            <thead>
              <tr>
                <th>Paciente</th>
                <th>Cédula</th>
                <th>Ingresó</th>
                <th>Plan activo</th>
                <th>Vence / Clases</th>
                <th>Estado</th>
                <th>Acciones</th>
              </tr>
            </thead>
            <tbody>
              {filtrados.map(m => {
                const { label, clase } = estadoBadge(m)
                const ma = m.membresia_activa
                return (
                  <tr key={m.id} className={rowClass(m)}>
                    <td className="td-nombre">{m.nombre} {m.apellido}</td>
                    <td>{m.cedula || '—'}</td>
                    <td>{formatFecha(m.fecha_ingreso)}</td>
                    <td>{ma?.plan_nombre ?? '—'}</td>
                    <td className="num">{venceDisplay(m)}</td>
                    <td><span className={`badge ${clase}`}>{label}</span></td>
                    <td className="td-acciones">
                      <button className="btn btn-sm btn-outline" onClick={() => abrirEditar(m)}>Editar</button>
                      <button className="btn btn-sm btn-outline" onClick={() => abrirPerfil(m)}>Perfil</button>
                      <button className="btn btn-sm btn-outline" onClick={() => abrirHistorial(m)}>Ver historial</button>
                      {m.activo
                        ? <button className="btn btn-sm btn-danger"  onClick={() => desactivar(m)}>Desactivar</button>
                        : <button className="btn btn-sm btn-outline" onClick={() => reactivar(m)}>Reactivar</button>
                      }
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      )}

      {/* ─── Modal crear/editar ─────────────────────────────────────────────── */}

      {modal && (
        <div className="modal-overlay" onClick={cerrarModal}>
          <div className="modal" ref={modalRef} tabIndex={-1} onClick={e => e.stopPropagation()}>
            <div className="modal-header">
              <h2>{modal === 'crear' ? 'Nuevo paciente' : 'Editar paciente'}</h2>
              <button className="modal-close" onClick={cerrarModal}>✕</button>
            </div>

            <form className="modal-form" onSubmit={guardar}>
              <div className="form-row">
                <label>
                  <span className="label-text">Nombre <span className="required">*</span></span>
                  <input name="nombre" value={form.nombre} onChange={handleChange} required />
                </label>
                <label>
                  <span className="label-text">Apellido <span className="required">*</span></span>
                  <input name="apellido" value={form.apellido} onChange={handleChange} required />
                </label>
              </div>

              <div className="form-row">
                <label>
                  <span className="label-text">Fecha de ingreso al centro <span className="required">*</span></span>
                  <input name="fecha_ingreso" type="date" value={form.fecha_ingreso} onChange={handleChange} required />
                </label>
                <label>
                  <span className="label-text">Cédula</span>
                  <input name="cedula" value={form.cedula} onChange={handleChange} />
                </label>
              </div>

              <div className="form-row">
                <label>
                  <span className="label-text">Teléfono</span>
                  <input name="telefono" value={form.telefono} onChange={handleChange} />
                </label>
                <label>
                  <span className="label-text">Email</span>
                  <input name="email" type="email" value={form.email} onChange={handleChange} />
                </label>
              </div>

              <div className="form-row">
                <label>
                  <span className="label-text">Fecha de nacimiento</span>
                  <input name="fecha_nacimiento" type="date" value={form.fecha_nacimiento} onChange={handleChange} />
                </label>
                <label>
                  <span className="label-text">Contacto de emergencia</span>
                  <input name="contacto_emergencia" value={form.contacto_emergencia} onChange={handleChange} placeholder="Nombre y teléfono" />
                </label>
              </div>

              <div className="form-row">
                <label>
                  <span className="label-text">Peso (kg)</span>
                  <input name="peso" type="number" step="0.1" min="0" value={form.peso} onChange={handleChange} />
                </label>
                <label>
                  <span className="label-text">Altura (cm)</span>
                  <input name="altura" type="number" step="0.1" min="0" value={form.altura} onChange={handleChange} />
                </label>
              </div>

              <label>
                <span className="label-text">Notas</span>
                <input name="notas" value={form.notas} onChange={handleChange} />
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

      {/* ─── Modal historial de pagos ───────────────────────────────────────── */}

      {histModal && (
        <div className="modal-overlay" onClick={cerrarHistorial}>
          <div className="modal modal-historial" ref={histModalRef} tabIndex={-1} onClick={e => e.stopPropagation()}>
            <div className="modal-header">
              <div>
                <h2>Historial de pagos</h2>
                <p className="historial-sub">{histModal.miembro.nombre} {histModal.miembro.apellido}</p>
              </div>
              <button className="modal-close" onClick={cerrarHistorial}>✕</button>
            </div>

            <div style={{ padding: '0 1.5rem 1.5rem' }}>
              {histModal.cargando ? (
                <p className="cargando">Cargando...</p>
              ) : histModal.error ? (
                <p className="estado-msg error">{histModal.error}</p>
              ) : histModal.membresias.length === 0 ? (
                <p className="vacio">Este paciente nunca tuvo una membresía.</p>
              ) : (
                <div style={{ display: 'flex', flexDirection: 'column', gap: '1.25rem' }}>
                  {histModal.membresias.map(mem => {
                    const { label, clase } = estadoMembresiaBadge(mem.estado)
                    return (
                      <div key={mem.id} style={{
                        border: '1px solid var(--color-border)', borderRadius: 10, padding: '0.9rem 1rem',
                      }}>
                        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: '0.5rem' }}>
                          <div>
                            <div style={{ fontWeight: 700 }}>{mem.plan?.nombre ?? 'Plan eliminado'}</div>
                            <div className="text-muted" style={{ fontSize: '0.8rem' }}>
                              {mem.fecha_fin
                                ? `${formatFecha(mem.fecha_inicio)} – ${formatFecha(mem.fecha_fin)}`
                                : `Desde ${formatFecha(mem.fecha_inicio)} · ${mem.clases_usadas}/${mem.clases_total ?? '—'} clases usadas`}
                            </div>
                          </div>
                          <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                            <span className={`badge ${clase}`}>{label}</span>
                            <a
                              className="btn btn-sm btn-outline"
                              href={facturasAPI.membresiaPdf(mem.id)}
                              target="_blank" rel="noreferrer"
                            >
                              Factura
                            </a>
                          </div>
                        </div>

                        <div style={{ display: 'flex', gap: '1.5rem', marginTop: '0.6rem', fontSize: '0.85rem' }}>
                          <span>Pagado: <strong className="num">${Number(mem.precio_pagado).toFixed(2)}</strong></span>
                          {mem.precio_acordado != null && Number(mem.precio_acordado) !== Number(mem.precio_pagado) && (
                            <span className="text-muted">
                              Acordado: <strong className="num">${Number(mem.precio_acordado).toFixed(2)}</strong>
                            </span>
                          )}
                          {mem.saldo > 0 && (
                            <span style={{ color: 'var(--color-danger)' }}>
                              Saldo: <strong className="num">${Number(mem.saldo).toFixed(2)}</strong>
                            </span>
                          )}
                        </div>

                        {mem.pagos.length === 0 ? (
                          <p className="text-muted" style={{ fontSize: '0.82rem', marginTop: '0.6rem', marginBottom: 0 }}>
                            Sin pagos registrados.
                          </p>
                        ) : (
                          <ul style={{ listStyle: 'none', display: 'flex', flexDirection: 'column', gap: '0.3rem', marginTop: '0.6rem' }}>
                            {mem.pagos.map(p => (
                              <li key={p.id} style={{
                                display: 'flex', alignItems: 'center', gap: '0.75rem', fontSize: '0.82rem',
                                background: 'var(--color-surface-alt)', borderRadius: 6, padding: '0.35rem 0.6rem',
                              }}>
                                <span className="text-muted" style={{ minWidth: 130 }}>{formatFechaHora(p.fecha)}</span>
                                <span className="text-muted">{fmtMetodoPago(p.metodo)}</span>
                                {p.notas && <span className="text-muted" style={{ flex: 1, fontStyle: 'italic' }}>{p.notas}</span>}
                                {p.comprobante_url && (
                                  <a href={p.comprobante_url} target="_blank" rel="noreferrer" style={{ color: 'var(--color-primary)', fontSize: '0.8rem' }}>
                                    Ver comprobante
                                  </a>
                                )}
                                <span className="num" style={{ marginLeft: 'auto', fontWeight: 700, color: 'var(--color-success-text)' }}>
                                  +${Number(p.monto).toFixed(2)}
                                </span>
                              </li>
                            ))}
                          </ul>
                        )}
                      </div>
                    )
                  })}
                </div>
              )}
            </div>
          </div>
        </div>
      )}

      {/* ─── Modal perfil (identidad + biometría + membresía + ficha médica) ── */}

      {perfilModal && (
        <div className="modal-overlay" onClick={cerrarPerfil}>
          <div className="modal modal-historial" ref={perfilModalRef} tabIndex={-1} onClick={e => e.stopPropagation()}>
            <div className="modal-header">
              <div>
                <h2>Perfil</h2>
                <p className="historial-sub">{perfilModal.miembro.nombre} {perfilModal.miembro.apellido}</p>
              </div>
              <button className="modal-close" onClick={cerrarPerfil}>✕</button>
            </div>

            <div style={{ padding: '0 1.5rem 1.5rem' }}>
              {(() => {
                const m = perfilModal.miembro
                const edad = calcularEdad(m.fecha_nacimiento)
                const imc = calcularIMC(m.peso, m.altura)
                const ma = m.membresia_activa
                return (
                  <div style={{
                    display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0.5rem 1.5rem',
                    border: '1px solid var(--color-border)', borderRadius: 10, padding: '1rem', marginBottom: '1.25rem',
                  }}>
                    <div><span className="text-muted">Cédula: </span>{m.cedula || '—'}</div>
                    <div><span className="text-muted">Edad: </span>{edad != null ? `${edad} años` : '—'}</div>
                    <div><span className="text-muted">Teléfono: </span>{m.telefono || '—'}</div>
                    <div><span className="text-muted">Contacto de emergencia: </span>{m.contacto_emergencia || '—'}</div>
                    <div><span className="text-muted">Peso: </span>{m.peso ? `${m.peso} kg` : '—'}</div>
                    <div><span className="text-muted">Altura: </span>{m.altura ? `${m.altura} cm` : '—'}</div>
                    <div style={{ gridColumn: '1 / -1' }}>
                      <span className="text-muted">IMC: </span>
                      {imc != null ? `${imc.toFixed(1)} (${categoriaIMC(imc)})` : '—'}
                    </div>
                    <div style={{ gridColumn: '1 / -1', borderTop: '1px solid var(--color-border)', paddingTop: '0.5rem', marginTop: '0.25rem' }}>
                      <span className="text-muted">Membresía: </span>
                      {ma ? (
                        <>
                          {ma.plan_nombre ?? 'Plan eliminado'}
                          {' — '}
                          <span className={`badge ${estadoMembresiaBadge(ma.estado).clase}`}>{estadoMembresiaBadge(ma.estado).label}</span>
                          {' · '}{venceDisplay(m)}
                        </>
                      ) : 'Sin plan activo'}
                    </div>
                  </div>
                )
              })()}

              <h3 style={{ fontSize: '0.95rem', marginBottom: '0.75rem' }}>Historial médico</h3>

              {perfilModal.cargando ? (
                <p className="cargando">Cargando...</p>
              ) : perfilModal.error ? (
                <p className="estado-msg error">{perfilModal.error}</p>
              ) : (
                <>
                  {perfilModal.historial.length === 0 ? (
                    <p className="vacio">Sin registros todavía.</p>
                  ) : (
                    <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem', marginBottom: '1rem' }}>
                      {perfilModal.historial.map(r => (
                        <div key={r.id} style={{
                          border: '1px solid var(--color-border)', borderRadius: 10, padding: '0.8rem 1rem',
                        }}>
                          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: '0.5rem' }}>
                            <div>
                              <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                                <span className="badge badge-inactivo">{TIPO_HISTORIAL[r.tipo] ?? r.tipo}</span>
                                {r.tipo === 'patologia' && (
                                  <span className={`badge ${r.activa ? 'badge-danger' : 'badge-ok'}`}>
                                    {r.activa ? 'En tratamiento' : 'Resuelta'}
                                  </span>
                                )}
                              </div>
                              <div style={{ fontWeight: 700, marginTop: '0.35rem' }}>{r.descripcion}</div>
                              <div className="text-muted" style={{ fontSize: '0.8rem' }}>
                                {r.fecha ? formatFecha(r.fecha) : 'Sin fecha registrada'}
                              </div>
                              {r.notas && (
                                <div className="text-muted" style={{ fontSize: '0.82rem', marginTop: '0.35rem', fontStyle: 'italic' }}>
                                  {r.notas}
                                </div>
                              )}
                            </div>
                            <button className="btn btn-sm btn-outline" onClick={() => eliminarRegistro(r.id)}>Eliminar</button>
                          </div>
                        </div>
                      ))}
                    </div>
                  )}

                  {!mostrarFormFicha ? (
                    <button className="btn btn-outline" onClick={() => setMostrarFormFicha(true)}>+ Agregar registro</button>
                  ) : (
                    <form className="modal-form" onSubmit={agregarRegistro} style={{ border: '1px solid var(--color-border)', borderRadius: 10, padding: '1rem' }}>
                      <div className="form-row">
                        <label>
                          <span className="label-text">Tipo <span className="required">*</span></span>
                          <select
                            value={nuevoRegistro.tipo}
                            onChange={e => setNuevoRegistro(f => ({ ...f, tipo: e.target.value }))}
                          >
                            {Object.entries(TIPO_HISTORIAL).map(([valor, label]) => (
                              <option key={valor} value={valor}>{label}</option>
                            ))}
                          </select>
                        </label>
                        <label>
                          <span className="label-text">Fecha</span>
                          <input
                            type="date"
                            value={nuevoRegistro.fecha}
                            onChange={e => setNuevoRegistro(f => ({ ...f, fecha: e.target.value }))}
                          />
                        </label>
                      </div>

                      <label>
                        <span className="label-text">Descripción <span className="required">*</span></span>
                        <input
                          value={nuevoRegistro.descripcion}
                          onChange={e => setNuevoRegistro(f => ({ ...f, descripcion: e.target.value }))}
                          placeholder="Ej. Fractura de tibia, Cirugía de rodilla..."
                          autoFocus
                        />
                      </label>

                      {nuevoRegistro.tipo === 'patologia' && (
                        <label style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', flexDirection: 'row' }}>
                          <input
                            type="checkbox"
                            checked={nuevoRegistro.activa}
                            onChange={e => setNuevoRegistro(f => ({ ...f, activa: e.target.checked }))}
                            style={{ width: 'auto' }}
                          />
                          <span className="label-text" style={{ margin: 0 }}>Sigue en tratamiento</span>
                        </label>
                      )}

                      <label>
                        <span className="label-text">Notas</span>
                        <input
                          value={nuevoRegistro.notas}
                          onChange={e => setNuevoRegistro(f => ({ ...f, notas: e.target.value }))}
                        />
                      </label>

                      <div className="modal-footer">
                        <button type="button" className="btn btn-outline" onClick={() => { setMostrarFormFicha(false); setNuevoRegistro(NUEVO_REGISTRO_VACIO) }}>
                          Cancelar
                        </button>
                        <button type="submit" className="btn btn-primary" disabled={guardandoRegistro}>
                          {guardandoRegistro ? 'Guardando...' : 'Guardar'}
                        </button>
                      </div>
                    </form>
                  )}
                </>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
