import { useState, useEffect } from 'react'
import { usuariosAPI } from '../services/api'
import { useFocusTrap } from '../hooks/useFocusTrap'
import './Clientes.css'

const FORM_VACIO = { email: '', nombre: '', password: '', rol: 'staff' }

export default function Usuarios() {
  const [usuarios,   setUsuarios]   = useState([])
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
      const res = await usuariosAPI.listar()
      setUsuarios(res.data)
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

  function abrirEditar(u) {
    setForm({ email: u.email, nombre: u.nombre, password: '', rol: u.rol })
    setEditandoId(u.id)
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

  async function guardar(e) {
    e.preventDefault()
    if (!form.nombre.trim()) return alert('El nombre es obligatorio.')

    try {
      setGuardando(true)
      if (modal === 'crear') {
        if (!form.email.trim())    return alert('El email es obligatorio.')
        if (!form.password.trim()) return alert('La contraseña es obligatoria.')
        await usuariosAPI.crear({
          email:    form.email.trim(),
          nombre:   form.nombre.trim(),
          password: form.password,
          rol:      form.rol,
        })
      } else {
        const payload = { nombre: form.nombre.trim(), rol: form.rol }
        if (form.password.trim()) payload.password = form.password.trim()
        await usuariosAPI.actualizar(editandoId, payload)
      }
      cerrarModal()
      cargar()
    } catch (err) {
      alert(err.response?.data?.detail ?? 'Error al guardar.')
    } finally {
      setGuardando(false)
    }
  }

  async function eliminar(u) {
    if (!confirm(`¿Eliminar al usuario "${u.nombre}"? Esta acción no se puede deshacer.`)) return
    try {
      await usuariosAPI.eliminar(u.id)
      cargar()
    } catch (err) {
      alert(err.response?.data?.detail ?? 'No se pudo eliminar el usuario.')
    }
  }

  return (
    <div className="page clientes">
      <div className="page-header">
        <h1>Usuarios</h1>
        <button className="btn btn-primary" onClick={abrirCrear}>+ Nuevo usuario</button>
      </div>

      {error && <p className="mensaje-error">{error}</p>}

      {cargando ? (
        <p className="cargando">Cargando...</p>
      ) : usuarios.length === 0 ? (
        <p className="vacio">No hay usuarios registrados.</p>
      ) : (
        <div className="tabla-wrapper">
          <table className="tabla">
            <thead>
              <tr>
                <th>Nombre</th>
                <th>Email</th>
                <th>Rol</th>
                <th>Estado</th>
                <th>Acciones</th>
              </tr>
            </thead>
            <tbody>
              {usuarios.map(u => (
                <tr key={u.id}>
                  <td className="td-nombre">{u.nombre}</td>
                  <td>{u.email}</td>
                  <td>
                    <span className={`badge ${u.rol === 'admin' ? 'badge-ok' : 'badge-warning'}`}>
                      {u.rol}
                    </span>
                  </td>
                  <td>
                    {u.activo
                      ? <span className="badge badge-ok">Activo</span>
                      : <span className="badge badge-inactivo">Inactivo</span>
                    }
                  </td>
                  <td className="td-acciones">
                    <button className="btn btn-sm btn-outline" onClick={() => abrirEditar(u)}>Editar</button>
                    <button className="btn btn-sm btn-danger"  onClick={() => eliminar(u)}>Eliminar</button>
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
              <h2>{modal === 'crear' ? 'Nuevo usuario' : 'Editar usuario'}</h2>
              <button className="modal-close" onClick={cerrarModal}>✕</button>
            </div>

            <form className="modal-form" onSubmit={guardar}>
              <label>
                <span className="label-text">Nombre <span className="required">*</span></span>
                <input name="nombre" value={form.nombre} onChange={handleChange} required />
              </label>

              {modal === 'crear' && (
                <label>
                  <span className="label-text">Email <span className="required">*</span></span>
                  <input name="email" type="email" value={form.email} onChange={handleChange} required />
                </label>
              )}

              <div className="form-row">
                <label>
                  <span className="label-text">
                    Contraseña {modal === 'crear' && <span className="required">*</span>}
                    {modal === 'editar' && <span className="label-hint"> (dejar vacío para no cambiar)</span>}
                  </span>
                  <input
                    name="password"
                    type="password"
                    value={form.password}
                    onChange={handleChange}
                    minLength={modal === 'crear' ? 8 : undefined}
                    required={modal === 'crear'}
                  />
                </label>
                <label>
                  <span className="label-text">Rol</span>
                  <select name="rol" value={form.rol} onChange={handleChange}>
                    <option value="staff">Staff</option>
                    <option value="admin">Admin</option>
                  </select>
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
