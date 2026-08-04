import { useState, useEffect, useCallback } from 'react'
import { instructoresAPI } from '../services/api'
import { useMonthNavigator } from '@shared/hooks/useMonthNavigator'
import { useFocusTrap } from '@shared/hooks/useFocusTrap'
import { MESES } from '@shared/utils/fecha'
import '@shared/pages/Clientes.css'

const FORM_VACIO = { nombre: '', telefono: '', tipo: 'doctor' }

const TIPO_LABEL = { entrenador: 'Entrenador', doctor: 'Doctor', asistente: 'Asistente' }

export default function Instructores() {
  const [instructores, setInstructores] = useState([])
  const [cargando,     setCargando]     = useState(true)
  const [error,        setError]        = useState(null)

  const [modal,      setModal]      = useState(null)  // 'crear' | 'editar'
  const [form,       setForm]       = useState(FORM_VACIO)
  const [editandoId, setEditandoId] = useState(null)
  const [guardando,  setGuardando]  = useState(false)
  const modalRef = useFocusTrap(!!modal)

  const { mes, anio, esMesActual, retroceder, avanzar } = useMonthNavigator()
  const [reporte,          setReporte]          = useState([])
  const [cargandoReporte,  setCargandoReporte]  = useState(true)

  // ─── Carga ──────────────────────────────────────────────────────────────────

  const cargar = useCallback(async () => {
    try {
      setCargando(true)
      setError(null)
      const res = await instructoresAPI.listar()
      setInstructores(res.data)
    } catch {
      setError('No se pudo conectar con el servidor.')
    } finally {
      setCargando(false)
    }
  }, [])

  useEffect(() => { cargar() }, [cargar])

  useEffect(() => {
    setCargandoReporte(true)
    instructoresAPI.reporte(mes, anio)
      .then(r => setReporte(r.data.instructores))
      .catch(() => setReporte([]))
      .finally(() => setCargandoReporte(false))
  }, [mes, anio])

  // ─── Modal crear/editar ─────────────────────────────────────────────────────

  function abrirCrear() {
    setForm(FORM_VACIO)
    setEditandoId(null)
    setModal('crear')
  }

  function abrirEditar(i) {
    setForm({ nombre: i.nombre, telefono: i.telefono ?? '', tipo: i.tipo })
    setEditandoId(i.id)
    setModal('editar')
  }

  function cerrarModal() {
    setModal(null)
    setForm(FORM_VACIO)
    setEditandoId(null)
  }

  function handleChange(e) {
    const { name, value } = e.target
    setForm(f => ({ ...f, [name]: value }))
  }

  async function guardar(e) {
    e.preventDefault()
    if (!form.nombre.trim()) return alert('El nombre es obligatorio.')
    try {
      setGuardando(true)
      const datos = { nombre: form.nombre.trim(), telefono: form.telefono.trim() || null, tipo: form.tipo }
      if (modal === 'crear') {
        await instructoresAPI.crear(datos)
      } else {
        await instructoresAPI.actualizar(editandoId, datos)
      }
      cerrarModal()
      await cargar()
    } catch (err) {
      alert(err.response?.data?.detail ?? 'No se pudo guardar el terapeuta.')
    } finally {
      setGuardando(false)
    }
  }

  async function alternarActivo(i) {
    try {
      if (i.activo) {
        if (!confirm(`¿Desactivar a "${i.nombre}"? Deja de aparecer como opción al programar citas nuevas.`)) return
        await instructoresAPI.desactivar(i.id)
      } else {
        await instructoresAPI.actualizar(i.id, { activo: true })
      }
      await cargar()
    } catch (err) {
      alert(err.response?.data?.detail ?? 'No se pudo actualizar el terapeuta.')
    }
  }

  async function eliminar(i) {
    if (!confirm(`¿Eliminar a "${i.nombre}" definitivamente? Esto no se puede deshacer.`)) return
    try {
      await instructoresAPI.eliminar(i.id)
      await cargar()
    } catch (err) {
      // 409 = tiene clientes atendidos — el backend explica que hay que
      // desactivarlo en vez de eliminarlo, se lo mostramos tal cual.
      alert(err.response?.data?.detail ?? 'No se pudo eliminar el terapeuta.')
    }
  }

  // ─── Render ─────────────────────────────────────────────────────────────────

  return (
    <div className="page clientes">
      <div className="page-header">
        <h1>Terapeutas</h1>
        <button className="btn btn-primary" onClick={abrirCrear}>+ Nuevo terapeuta</button>
      </div>

      {error && <p className="mensaje-error">{error}</p>}

      {cargando ? (
        <p className="cargando">Cargando...</p>
      ) : instructores.length === 0 ? (
        <p className="vacio">No hay terapeutas registrados todavía.</p>
      ) : (
        <div className="tabla-wrapper">
          <table className="tabla">
            <thead>
              <tr>
                <th>Nombre</th>
                <th>Tipo</th>
                <th>Teléfono</th>
                <th>Estado</th>
                <th>Acciones</th>
              </tr>
            </thead>
            <tbody>
              {instructores.map(i => (
                <tr key={i.id}>
                  <td className="td-nombre">{i.nombre}</td>
                  <td>{TIPO_LABEL[i.tipo] ?? i.tipo}</td>
                  <td>{i.telefono || '—'}</td>
                  <td>
                    <span className={`badge ${i.activo ? 'badge-ok' : 'badge-inactivo'}`}>
                      {i.activo ? 'Vigente' : 'Inactivo'}
                    </span>
                  </td>
                  <td className="td-acciones">
                    <button className="btn btn-sm btn-outline" onClick={() => abrirEditar(i)}>Editar</button>
                    <button className="btn btn-sm btn-outline" onClick={() => alternarActivo(i)}>
                      {i.activo ? 'Desactivar' : 'Reactivar'}
                    </button>
                    <button className="btn btn-sm btn-outline" onClick={() => eliminar(i)} title="Eliminar definitivamente — solo si nunca tuvo pacientes asignados">
                      Eliminar
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* ── Clientes atendidos por instructor ────────────────────────────── */}
      <div style={{ marginTop: '2rem' }}>
        <div className="page-header" style={{ marginBottom: '0.75rem' }}>
          <h2 style={{ fontSize: '1.1rem', margin: 0 }}>Pacientes atendidos por terapeuta</h2>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
            <button className="btn btn-sm btn-outline" onClick={retroceder} title="Mes anterior">‹</button>
            <span style={{ fontSize: '0.9rem', minWidth: 130, textAlign: 'center' }}>
              {MESES[mes - 1]} {anio}
            </span>
            <button
              className="btn btn-sm btn-outline"
              onClick={avanzar}
              disabled={esMesActual}
              title={esMesActual ? 'Es el mes actual' : 'Mes siguiente'}
            >›</button>
          </div>
        </div>

        <p className="text-muted" style={{ fontSize: '0.8rem', marginBottom: '0.75rem' }}>
          Pacientes distintos que asistieron con cada terapeuta en el mes — no citas dictadas
          (un mismo paciente que vino 8 veces con el mismo terapeuta cuenta una sola vez).
        </p>

        {cargandoReporte ? (
          <p className="cargando">Cargando...</p>
        ) : reporte.length === 0 ? (
          <p className="vacio">No hay terapeutas vigentes para mostrar.</p>
        ) : (
          <div className="tabla-wrapper">
            <table className="tabla">
              <thead>
                <tr>
                  <th>Terapeuta</th>
                  <th>Pacientes atendidos</th>
                </tr>
              </thead>
              <tbody>
                {reporte.map(r => (
                  <tr key={r.instructor_id}>
                    <td className="td-nombre">{r.nombre}</td>
                    <td className="num">{r.clientes}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* ── Modal crear/editar ───────────────────────────────────────────── */}
      {modal && (
        <div className="modal-overlay" onClick={cerrarModal}>
          <div className="modal" ref={modalRef} tabIndex={-1} onClick={e => e.stopPropagation()}>
            <div className="modal-header">
              <h2>{modal === 'crear' ? 'Nuevo terapeuta' : 'Editar terapeuta'}</h2>
              <button className="modal-close" onClick={cerrarModal}>✕</button>
            </div>

            <form className="modal-form" onSubmit={guardar}>
              <label>
                <span className="label-text">Nombre <span className="required">*</span></span>
                <input name="nombre" value={form.nombre} onChange={handleChange} required autoFocus />
              </label>
              <label>
                <span className="label-text">Tipo <span className="required">*</span></span>
                <select name="tipo" value={form.tipo} onChange={handleChange} required>
                  <option value="entrenador">Entrenador</option>
                  <option value="doctor">Doctor</option>
                  <option value="asistente">Asistente</option>
                </select>
              </label>
              <label>
                <span className="label-text">Teléfono</span>
                <input name="telefono" value={form.telefono} onChange={handleChange} />
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
    </div>
  )
}
