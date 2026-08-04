import { useState, useEffect } from 'react'
import { planesAPI } from '../services/api'
import { useFocusTrap } from '../hooks/useFocusTrap'
import './Clientes.css'

const TIPO_LABELS = { tiempo: 'Por tiempo', clases: 'Por clases' }

const FORM_VACIO = { nombre: '', tipo: 'tiempo', duracion_dias: '', clases_total: '', precio: '' }

export default function Planes() {
  const [planes,     setPlanes]     = useState([])
  const [cargando,   setCargando]   = useState(true)
  const [error,      setError]      = useState(null)
  const [modal,      setModal]      = useState(null)  // 'crear' | 'editar'
  const [form,       setForm]       = useState(FORM_VACIO)
  const [editandoId, setEditandoId] = useState(null)
  const [guardando,  setGuardando]  = useState(false)

  const modalRef = useFocusTrap(!!modal)

  async function cargar() {
    try {
      setCargando(true)
      setError(null)
      const res = await planesAPI.listarTodos()
      setPlanes(res.data)
    } catch {
      setError('No se pudo conectar con el servidor.')
    } finally {
      setCargando(false)
    }
  }

  useEffect(() => { cargar() }, [])

  function abrirCrear() {
    setForm(FORM_VACIO)
    setEditandoId(null)
    setModal('crear')
  }

  function abrirEditar(p) {
    setForm({
      nombre:        p.nombre        ?? '',
      tipo:          p.tipo          ?? 'tiempo',
      duracion_dias: p.duracion_dias ?? '',
      clases_total:  p.clases_total  ?? '',
      precio:        p.precio        ?? '',
    })
    setEditandoId(p.id)
    setModal('editar')
  }

  function cerrarModal() {
    setModal(null)
    setForm(FORM_VACIO)
    setEditandoId(null)
  }

  function handleChange(e) {
    const { name, value } = e.target
    setForm(prev => ({
      ...prev,
      [name]: value,
      ...(name === 'tipo' ? { duracion_dias: '', clases_total: '' } : {}),
    }))
  }

  async function guardar(e) {
    e.preventDefault()
    if (!form.nombre.trim()) return alert('El nombre es obligatorio.')
    if (!form.precio)        return alert('El precio es obligatorio.')

    const payload = modal === 'crear'
      ? {
          nombre: form.nombre.trim(),
          tipo:   form.tipo,
          precio: parseFloat(form.precio),
          ...(form.tipo === 'tiempo'
            ? { duracion_dias: parseInt(form.duracion_dias) }
            : { clases_total:  parseInt(form.clases_total) }),
        }
      : {
          nombre: form.nombre.trim(),
          precio: parseFloat(form.precio),
          ...(form.duracion_dias ? { duracion_dias: parseInt(form.duracion_dias) } : {}),
          ...(form.clases_total  ? { clases_total:  parseInt(form.clases_total)  } : {}),
        }

    try {
      setGuardando(true)
      if (modal === 'crear') {
        await planesAPI.crear(payload)
      } else {
        await planesAPI.actualizar(editandoId, payload)
      }
      cerrarModal()
      cargar()
    } catch (err) {
      alert(err.response?.data?.detail ?? 'Error al guardar.')
    } finally {
      setGuardando(false)
    }
  }

  async function desactivar(p) {
    if (!confirm(`¿Desactivar el plan "${p.nombre}"? Las membresías activas no se ven afectadas.`)) return
    try {
      await planesAPI.desactivar(p.id)
      cargar()
    } catch (err) {
      alert(err.response?.data?.detail ?? 'No se pudo desactivar el plan.')
    }
  }

  return (
    <div className="page clientes">
      <div className="page-header">
        <h1>Planes</h1>
        <button className="btn btn-primary" onClick={abrirCrear}>+ Nuevo plan</button>
      </div>

      {error && <p className="mensaje-error">{error}</p>}

      {cargando ? (
        <p className="cargando">Cargando...</p>
      ) : planes.length === 0 ? (
        <p className="vacio">No hay planes registrados.</p>
      ) : (
        <div className="tabla-wrapper">
          <table className="tabla">
            <thead>
              <tr>
                <th>Nombre</th>
                <th>Tipo</th>
                <th>Duración / Clases</th>
                <th>Precio</th>
                <th>Estado</th>
                <th>Acciones</th>
              </tr>
            </thead>
            <tbody>
              {planes.map(p => (
                <tr key={p.id}>
                  <td className="td-nombre">{p.nombre}</td>
                  <td>{TIPO_LABELS[p.tipo] ?? p.tipo}</td>
                  <td>
                    {p.tipo === 'tiempo'
                      ? `${p.duracion_dias} días`
                      : `${p.clases_total} clases`}
                  </td>
                  <td className="num">${parseFloat(p.precio).toFixed(2)}</td>
                  <td>
                    {p.activo
                      ? <span className="badge badge-ok">Activo</span>
                      : <span className="badge badge-inactivo">Inactivo</span>
                    }
                  </td>
                  <td className="td-acciones">
                    <button className="btn btn-sm btn-outline" onClick={() => abrirEditar(p)}>Editar</button>
                    {p.activo && (
                      <button className="btn btn-sm btn-danger" onClick={() => desactivar(p)}>Desactivar</button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {modal && (
        <div className="modal-overlay" onClick={cerrarModal}>
          <div className="modal" ref={modalRef} tabIndex={-1} onClick={e => e.stopPropagation()}>
            <div className="modal-header">
              <h2>{modal === 'crear' ? 'Nuevo plan' : 'Editar plan'}</h2>
              <button className="modal-close" onClick={cerrarModal}>✕</button>
            </div>

            <form className="modal-form" onSubmit={guardar}>
              <label>
                <span className="label-text">Nombre <span className="required">*</span></span>
                <input name="nombre" value={form.nombre} onChange={handleChange} required />
              </label>

              {modal === 'crear' && (
                <label>
                  <span className="label-text">Tipo <span className="required">*</span></span>
                  <select name="tipo" value={form.tipo} onChange={handleChange}>
                    <option value="tiempo">Por tiempo</option>
                    <option value="clases">Por clases</option>
                  </select>
                </label>
              )}

              <div className="form-row">
                {form.tipo === 'tiempo' ? (
                  <label>
                    <span className="label-text">Duración (días) <span className="required">*</span></span>
                    <input
                      name="duracion_dias"
                      type="number"
                      min="1"
                      value={form.duracion_dias}
                      onChange={handleChange}
                      placeholder="30"
                      required={modal === 'crear'}
                    />
                  </label>
                ) : (
                  <label>
                    <span className="label-text">Clases totales <span className="required">*</span></span>
                    <input
                      name="clases_total"
                      type="number"
                      min="1"
                      value={form.clases_total}
                      onChange={handleChange}
                      placeholder="10"
                      required={modal === 'crear'}
                    />
                  </label>
                )}
                <label>
                  <span className="label-text">Precio <span className="required">*</span></span>
                  <input
                    name="precio"
                    type="number"
                    step="0.01"
                    min="0"
                    value={form.precio}
                    onChange={handleChange}
                    placeholder="0.00"
                    required
                  />
                </label>
              </div>

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
