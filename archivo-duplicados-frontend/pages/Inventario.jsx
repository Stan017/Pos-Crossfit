import { useState, useEffect, useCallback, useRef } from 'react'
import { productosAPI } from '../services/api'
import { useFocusTrap } from '../hooks/useFocusTrap'
import './Inventario.css'

const MAX_MB = 5

const PRODUCTO_VACIO = {
  nombre: '', categoria: '', codigo_barra: '',
  precio_venta: '', precio_costo: '', stock: '', stock_minimo: '',
  imagen_url: '',
}

export default function Inventario() {
  const [productos, setProductos]     = useState([])
  const [busqueda, setBusqueda]       = useState('')
  const [cargando, setCargando]       = useState(true)
  const [error, setError]             = useState(null)
  const [modal, setModal]             = useState(null)
  const [form, setForm]               = useState(PRODUCTO_VACIO)
  const [editandoId, setEditandoId]   = useState(null)
  const [guardando, setGuardando]     = useState(false)
  const [subiendoImg, setSubiendoImg] = useState(false)
  const inputFileRef                  = useRef(null)
  const modalRef                      = useFocusTrap(!!modal)

  // Categorías dinámicas
  const [categorias, setCategorias]                 = useState([])
  const [nuevaCategoria, setNuevaCategoria]         = useState('')
  const [agregandoCategoria, setAgregandoCategoria] = useState(false)
  const inputNuevaCategoriaRef                      = useRef(null)

  // ─── Carga ──────────────────────────────────────────────────────────────────

  const cargarProductos = useCallback(async (q = busqueda) => {
    try {
      setCargando(true)
      setError(null)
      const res = await productosAPI.listar(q)
      setProductos(res.data)
    } catch {
      setError('No se pudo conectar con el servidor.')
    } finally {
      setCargando(false)
    }
  }, [busqueda])

  async function cargarCategorias() {
    try {
      const res = await productosAPI.categorias()
      setCategorias(res.data)
    } catch {
      setCategorias([])
    }
  }

  useEffect(() => { cargarProductos('') }, [])

  // El montaje ya dispara la carga de arriba — sin este guard, este efecto
  // también corre en el montaje (todo efecto corre al montar sin importar
  // sus dependencias) y programa una segunda carga idéntica 300ms después.
  const primeraCargaDebounce = useRef(true)
  useEffect(() => {
    if (primeraCargaDebounce.current) { primeraCargaDebounce.current = false; return }
    const t = setTimeout(() => cargarProductos(busqueda), 300)
    return () => clearTimeout(t)
  }, [busqueda])

  // Bloquea el scroll del body cuando el modal está abierto
  useEffect(() => {
    if (modal) {
      document.body.style.overflow = 'hidden'
    } else {
      document.body.style.overflow = ''
    }
    return () => { document.body.style.overflow = '' }
  }, [modal])

  // ─── Modal ──────────────────────────────────────────────────────────────────

  function abrirCrear() {
    setForm(PRODUCTO_VACIO)
    setEditandoId(null)
    setAgregandoCategoria(false); setNuevaCategoria('')
    cargarCategorias()
    setModal('crear')
  }

  function abrirEditar(p) {
    setForm({
      nombre:        p.nombre        ?? '',
      categoria:     p.categoria     ?? '',
      codigo_barra:  p.codigo_barra  ?? '',
      precio_venta:  p.precio_venta  ?? '',
      precio_costo:  p.precio_costo  ?? '',
      stock:         p.stock         ?? '',
      stock_minimo:  p.stock_minimo  ?? '',
      imagen_url:    p.imagen_url    ?? '',
    })
    setEditandoId(p.id)
    setAgregandoCategoria(false); setNuevaCategoria('')
    cargarCategorias()
    setModal('editar')
  }

  function cerrarModal() {
    setModal(null)
    setForm(PRODUCTO_VACIO)
    setEditandoId(null)
    setAgregandoCategoria(false); setNuevaCategoria('')
  }

  function handleChange(e) {
    const { name, value } = e.target
    if (name === 'categoria' && value === '__nueva__') {
      setAgregandoCategoria(true)
      setTimeout(() => inputNuevaCategoriaRef.current?.focus(), 50)
      return
    }
    setForm(prev => ({ ...prev, [name]: value }))
  }

  function confirmarNuevaCategoria() {
    const nombre = nuevaCategoria.trim()
    if (!nombre) return
    if (!categorias.includes(nombre)) setCategorias(prev => [...prev, nombre].sort())
    setForm(prev => ({ ...prev, categoria: nombre }))
    setAgregandoCategoria(false); setNuevaCategoria('')
  }

  function cancelarNuevaCategoria() {
    setAgregandoCategoria(false); setNuevaCategoria('')
    setForm(prev => ({ ...prev, categoria: '' }))
  }

  // ─── Guardar ────────────────────────────────────────────────────────────────

  async function guardar(e) {
    e.preventDefault()
    if (!form.nombre.trim())      return alert('El nombre es obligatorio.')
    if (form.precio_venta === '') return alert('El precio de venta es obligatorio.')
    if (form.precio_costo === '') return alert('El precio de costo es obligatorio.')

    const payload = {
      nombre:       form.nombre.trim(),
      categoria:    form.categoria    || null,
      codigo_barra: form.codigo_barra.trim() || null,
      precio_venta: parseFloat(form.precio_venta),
      precio_costo: parseFloat(form.precio_costo),
      stock:        parseInt(form.stock || 0, 10),
      stock_minimo: parseInt(form.stock_minimo || 0, 10),
      imagen_url:   form.imagen_url.trim() || null,
    }

    try {
      setGuardando(true)
      if (modal === 'crear') {
        await productosAPI.crear(payload)
      } else {
        await productosAPI.actualizar(editandoId, payload)
      }
      cerrarModal()
      cargarProductos(busqueda)
    } catch (err) {
      alert(err.response?.data?.detail ?? 'Error al guardar.')
    } finally {
      setGuardando(false)
    }
  }

  // ─── Eliminar ───────────────────────────────────────────────────────────────

  async function eliminar(p) {
    if (!confirm(`¿Eliminar "${p.nombre}"?`)) return
    try {
      await productosAPI.eliminar(p.id)
      cargarProductos(busqueda)
    } catch {
      alert('No se pudo eliminar el producto.')
    }
  }

  // ─── Utilidades ─────────────────────────────────────────────────────────────

  function margenPct(p) {
    if (!p.precio_costo || p.precio_costo === 0) return '—'
    return (((p.precio_venta - p.precio_costo) / p.precio_costo) * 100).toFixed(1) + '%'
  }

  function claseStock(p) {
    if (p.stock === 0) return 'badge badge-danger'
    if (p.stock <= p.stock_minimo) return 'badge badge-warning'
    return 'badge badge-ok'
  }

  // ─── Render ─────────────────────────────────────────────────────────────────

  return (
    <div className="page inventario">
      <div className="page-header">
        <h1>Inventario</h1>
        <div className="header-acciones">
          <button className="btn btn-primary" onClick={abrirCrear}>+ Nuevo producto</button>
        </div>
      </div>

      <div className="toolbar">
        <input
          className="input-busqueda"
          type="text"
          placeholder="Buscar por nombre, categoría o código de barra..."
          value={busqueda}
          onChange={e => setBusqueda(e.target.value)}
        />
        <span className="total-label">
          {productos.length} producto{productos.length !== 1 ? 's' : ''}
          {' '}&nbsp;|&nbsp;{' '}
          {productos.reduce((s, p) => s + (p.stock || 0), 0)} items
        </span>
      </div>

      {error && <p className="mensaje-error">{error}</p>}

      {cargando ? (
        <p className="cargando">Cargando...</p>
      ) : productos.length === 0 ? (
        <p className="vacio">
          {busqueda ? 'Sin resultados para esa búsqueda.' : 'No hay productos registrados.'}
        </p>
      ) : (
        <div className="tabla-wrapper">
          <table className="tabla">
            <thead>
              <tr>
                <th className="th-img"></th>
                <th>Nombre</th>
                <th>Categoría</th>
                <th>Código de barra</th>
                <th>Costo</th>
                <th>Venta</th>
                <th>Margen</th>
                <th>Stock</th>
                <th className="th-acciones">Acciones</th>
              </tr>
            </thead>
            <tbody>
              {productos.map(p => (
                <tr key={p.id}>
                  <td className="td-img">
                    {p.imagen_url
                      ? <img src={p.imagen_url} alt={p.nombre} className="tabla-thumbnail" />
                      : <span className="sin-thumbnail">📦</span>
                    }
                  </td>
                  <td className="td-nombre">{p.nombre}</td>
                  <td>{p.categoria || '—'}</td>
                  <td>{p.codigo_barra || '—'}</td>
                  <td className="num">${p.precio_costo.toFixed(2)}</td>
                  <td className="num">${p.precio_venta.toFixed(2)}</td>
                  <td className="num">{margenPct(p)}</td>
                  <td>
                    <span className={`${claseStock(p)} num`}>
                      {p.stock === 0 ? 'Sin stock' : p.stock}
                    </span>
                  </td>
                  <td className="td-acciones">
                    <div className="acciones-btns">
                      <button className="btn btn-sm btn-outline" onClick={() => abrirEditar(p)}>Editar</button>
                      <button className="btn btn-sm btn-danger"  onClick={() => eliminar(p)}>Eliminar</button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* ─── Modal ─────────────────────────────────────────────────────────── */}

      {modal && (
        <div className="modal-overlay" onClick={cerrarModal}>
          <div className="modal" ref={modalRef} tabIndex={-1} onClick={e => e.stopPropagation()}>
            <div className="modal-header">
              <h2>{modal === 'crear' ? 'Nuevo producto' : 'Editar producto'}</h2>
              <button className="modal-close" onClick={cerrarModal}>✕</button>
            </div>

            <form className="modal-form" onSubmit={guardar}>

              {/* Fila 1: Nombre + Categoría */}
              <div className="form-row">
                <label>
                  <span className="label-text">Nombre <span className="required">*</span></span>
                  <input name="nombre" value={form.nombre} onChange={handleChange} required />
                </label>

                <label>
                  <span className="label-text">Categoría</span>
                  {agregandoCategoria ? (
                    <div className="nueva-categoria-row">
                      <input
                        ref={inputNuevaCategoriaRef}
                        value={nuevaCategoria}
                        onChange={e => setNuevaCategoria(e.target.value)}
                        onKeyDown={e => e.key === 'Enter' && (e.preventDefault(), confirmarNuevaCategoria())}
                        placeholder="Nueva categoría"
                      />
                      <button type="button" className="btn-cat-ok"     onClick={confirmarNuevaCategoria}>✓</button>
                      <button type="button" className="btn-cat-cancel" onClick={cancelarNuevaCategoria}>✕</button>
                    </div>
                  ) : (
                    <select name="categoria" value={form.categoria} onChange={handleChange}>
                      <option value="">— Seleccionar —</option>
                      {categorias.map(c => <option key={c} value={c}>{c}</option>)}
                      <option value="__nueva__">+ Añadir categoría</option>
                    </select>
                  )}
                </label>
              </div>

              {/* Fila 2: Precio costo + Precio venta */}
              <div className="form-row">
                <label>
                  <span className="label-text">Precio de costo <span className="required">*</span></span>
                  <input name="precio_costo" type="number" step="0.01" min="0" value={form.precio_costo} onChange={handleChange} required />
                </label>
                <label>
                  <span className="label-text">Precio de venta <span className="required">*</span></span>
                  <input name="precio_venta" type="number" step="0.01" min="0" value={form.precio_venta} onChange={handleChange} required />
                </label>
              </div>

              {/* Fila 3: Stock + Stock mínimo */}
              <div className="form-row">
                <label>
                  <span className="label-text">Stock</span>
                  <input name="stock" type="number" min="0" value={form.stock} onChange={handleChange} />
                </label>
                <label>
                  <span className="label-text">Stock mínimo <span className="field-hint">(alerta de stock bajo)</span></span>
                  <input name="stock_minimo" type="number" min="0" value={form.stock_minimo} onChange={handleChange} />
                </label>
              </div>

              {/* Código de barra — ancho completo */}
              <label className="form-row-full">
                <span className="label-text">Código de barra</span>
                <input
                  name="codigo_barra"
                  value={form.codigo_barra}
                  onChange={handleChange}
                  placeholder="ej: 7861234567890"
                  maxLength={100}
                />
              </label>

              {/* Imagen del producto */}
              <div className="form-imagen">
                <span className="label-text">Imagen del producto</span>

                {/* Input file oculto */}
                <input
                  ref={inputFileRef}
                  type="file"
                  accept="image/jpeg,image/png,image/webp"
                  style={{ display: 'none' }}
                  onChange={async e => {
                    const file = e.target.files[0]
                    if (!file) return
                    if (file.size > MAX_MB * 1024 * 1024) {
                      alert(`La imagen no puede superar ${MAX_MB}MB`)
                      return
                    }
                    if (!editandoId) {
                      alert('Guarda el producto primero para poder subir la imagen.')
                      return
                    }
                    try {
                      setSubiendoImg(true)
                      const res = await productosAPI.subirImagen(editandoId, file)
                      setForm(p => ({ ...p, imagen_url: res.data.imagen_url }))
                    } catch {
                      alert('Error al subir la imagen. Verifica tu conexión.')
                    } finally {
                      setSubiendoImg(false)
                      e.target.value = ''
                    }
                  }}
                />

                {form.imagen_url ? (
                  <div className="imagen-con-preview">
                    <img
                      src={form.imagen_url}
                      alt="preview"
                      className="imagen-preview"
                      onError={e => { e.target.style.display = 'none' }}
                    />
                    <div className="imagen-inputs">
                      <button
                        type="button"
                        className="btn-cambiar-imagen"
                        onClick={() => inputFileRef.current?.click()}
                        disabled={subiendoImg || !editandoId}
                      >
                        {subiendoImg ? 'Subiendo...' : '🔄 Cambiar foto'}
                      </button>
                      <button
                        type="button"
                        className="btn-quitar-imagen"
                        onClick={() => setForm(p => ({ ...p, imagen_url: '' }))}
                      >
                        Quitar imagen
                      </button>
                    </div>
                  </div>
                ) : (
                  <div className="imagen-vacia">
                    <span className="imagen-vacia-icono">🖼️</span>
                    <button
                      type="button"
                      className="btn-subir-imagen"
                      onClick={() => inputFileRef.current?.click()}
                      disabled={subiendoImg || !editandoId}
                    >
                      {subiendoImg
                        ? 'Subiendo...'
                        : editandoId
                          ? '📤 Subir foto'
                          : '💾 Guarda el producto primero'
                      }
                    </button>
                    {!editandoId && (
                      <span className="imagen-hint">
                        Crea el producto y luego edítalo para subir la foto
                      </span>
                    )}
                  </div>
                )}
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
