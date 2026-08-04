import { useState, useEffect, useCallback } from 'react'
import { ventasAPI, membresiasAPI, facturasAPI } from '../services/api'
import { formatFecha, formatFechaHora } from '@shared/utils/fecha'
import { fmtMetodoPago, estadoMembresiaBadge } from '@shared/utils/formato'
import { useFocusTrap } from '@shared/hooks/useFocusTrap'
import '@shared/pages/Clientes.css'

const FILTROS_TIPO = [
  { value: 'todos',     label: 'Todos'      },
  { value: 'venta',     label: 'Ventas'     },
  { value: 'membresia', label: 'Membresías' },
]

const COSTO_EXTRA_VACIO = { descripcion: '', monto: '', notas: '' }

function nombreClienteVenta(v) {
  return v.miembro ? `${v.miembro.nombre} ${v.miembro.apellido}` : 'Consumidor Final'
}

function nombreClienteMembresia(m) {
  return m.miembro ? `${m.miembro.nombre} ${m.miembro.apellido}` : `#${m.miembro_id}`
}

function estadoBadgeVenta(estado) {
  if (estado === 'pagada')    return { label: 'Pagada',    clase: 'badge-ok'       }
  if (estado === 'abono')     return { label: 'En abono',  clase: 'badge-warning'  }
  if (estado === 'cancelada') return { label: 'Cancelada', clase: 'badge-inactivo' }
  return { label: estado, clase: 'badge-inactivo' }
}

function nombreItem(item) {
  return item.producto ? item.producto.nombre : (item.descripcion_libre || 'Costo extra')
}

export default function Cobros() {
  const [cobros,     setCobros]     = useState([])
  const [busqueda,   setBusqueda]   = useState('')
  const [tipoFiltro, setTipoFiltro] = useState('todos')
  const [cargando,   setCargando]   = useState(true)
  const [error,      setError]      = useState(null)

  const [detalleModal, setDetalleModal]         = useState(null)  // { tipo, ...datos }
  const [cargandoPagosMem, setCargandoPagosMem] = useState(false)

  const [costoExtraModal, setCostoExtraModal] = useState(null)  // venta
  const [costoExtraForm,  setCostoExtraForm]  = useState(COSTO_EXTRA_VACIO)
  const [guardandoCosto,  setGuardandoCosto]  = useState(false)
  const [costoExtraError, setCostoExtraError] = useState(null)

  const detalleModalRef    = useFocusTrap(!!detalleModal)
  const costoExtraModalRef = useFocusTrap(!!costoExtraModal)

  // ─── Carga ──────────────────────────────────────────────────────────────────
  // Se fusionan ventas + membresías en el cliente en vez de un endpoint nuevo:
  // ambos ya vienen completos de GET /ventas/ y GET /membresias/, no hay
  // lógica de negocio nueva que justifique un endpoint de "cobros" en el back.

  const cargar = useCallback(async () => {
    try {
      setCargando(true)
      setError(null)
      const [rVentas, rMembresias] = await Promise.all([
        ventasAPI.listar(),
        membresiasAPI.listar(),
      ])
      const ventas      = rVentas.data.map(v => ({ ...v, tipo: 'venta' }))
      const membresias  = rMembresias.data.map(m => ({ ...m, tipo: 'membresia' }))
      const todos = [...ventas, ...membresias].sort(
        (a, b) => new Date(b.creado_en) - new Date(a.creado_en)
      )
      setCobros(todos)
    } catch {
      setError('No se pudo conectar con el servidor.')
    } finally {
      setCargando(false)
    }
  }, [])

  useEffect(() => { cargar() }, [cargar])

  // ─── Filtro local ───────────────────────────────────────────────────────────

  const filtrados = cobros.filter(c => {
    if (tipoFiltro !== 'todos' && c.tipo !== tipoFiltro) return false
    if (!busqueda.trim()) return true
    const nombre = c.tipo === 'venta' ? nombreClienteVenta(c) : nombreClienteMembresia(c)
    return nombre.toLowerCase().includes(busqueda.trim().toLowerCase())
  })

  const conteos = FILTROS_TIPO.reduce((acc, f) => {
    acc[f.value] = f.value === 'todos' ? cobros.length : cobros.filter(c => c.tipo === f.value).length
    return acc
  }, {})

  // ─── Detalle ────────────────────────────────────────────────────────────────
  // listar_ventas ya trae items+pagos completos — sin fetch extra. listar_membresias
  // NO trae pagos (para no cargar esa lista en cada fila); se piden recién acá,
  // al abrir el detalle de una membresía puntual.

  function abrirDetalle(c) {
    if (c.tipo === 'venta') {
      setDetalleModal(c)
      return
    }
    setDetalleModal({ ...c, pagos: [] })
    setCargandoPagosMem(true)
    membresiasAPI.listarPagos(c.id)
      .then(res => setDetalleModal(prev => (prev && prev.id === c.id ? { ...prev, pagos: res.data } : prev)))
      .finally(() => setCargandoPagosMem(false))
  }

  // ─── Costo extra (solo ventas) ────────────────────────────────────────────

  function abrirCostoExtra(v) {
    setCostoExtraModal(v)
    setCostoExtraForm(COSTO_EXTRA_VACIO)
    setCostoExtraError(null)
  }

  async function confirmarCostoExtra(e) {
    e.preventDefault()
    if (!costoExtraForm.descripcion.trim()) {
      setCostoExtraError('Ingresa una descripción.')
      return
    }
    const monto = parseFloat(costoExtraForm.monto)
    if (!monto || monto <= 0) {
      setCostoExtraError('Ingresa un monto válido.')
      return
    }
    try {
      setGuardandoCosto(true)
      setCostoExtraError(null)
      await ventasAPI.agregarCostoExtra(costoExtraModal.id, {
        descripcion: costoExtraForm.descripcion.trim(),
        monto,
        notas: costoExtraForm.notas.trim() || undefined,
      })
      setCostoExtraModal(null)
      await cargar()
    } catch (err) {
      setCostoExtraError(err.response?.data?.detail ?? 'No se pudo agregar el costo extra.')
    } finally {
      setGuardandoCosto(false)
    }
  }

  // ─── Render ─────────────────────────────────────────────────────────────────

  return (
    <div className="page clientes">
      <div className="page-header">
        <h1>Cobros</h1>
      </div>

      <div className="toolbar">
        <input
          className="input-busqueda"
          type="text"
          placeholder="Buscar por cliente..."
          value={busqueda}
          onChange={e => setBusqueda(e.target.value)}
        />
        <div className="filtros">
          {FILTROS_TIPO.map(f => (
            <button
              key={f.value}
              className={`btn-filtro ${tipoFiltro === f.value ? 'activo' : ''}`}
              onClick={() => setTipoFiltro(f.value)}
            >
              {f.label}
              {conteos[f.value] > 0 && <span style={{ marginLeft: '0.3rem', opacity: 0.7 }}>({conteos[f.value]})</span>}
            </button>
          ))}
        </div>
        <span className="total-label">{filtrados.length} cobro{filtrados.length !== 1 ? 's' : ''}</span>
      </div>

      {error && <p className="mensaje-error">{error}</p>}

      {cargando ? (
        <p className="cargando">Cargando...</p>
      ) : filtrados.length === 0 ? (
        <p className="vacio">{busqueda ? 'Sin resultados.' : 'No hay cobros en este filtro.'}</p>
      ) : (
        <div className="tabla-wrapper">
          <table className="tabla">
            <thead>
              <tr>
                <th>Fecha</th>
                <th>Tipo</th>
                <th>Cliente</th>
                <th>Concepto</th>
                <th>Monto</th>
                <th>Estado</th>
                <th>Acciones</th>
              </tr>
            </thead>
            <tbody>
              {filtrados.map(c => {
                const esVenta = c.tipo === 'venta'
                const { label, clase } = esVenta ? estadoBadgeVenta(c.estado) : estadoMembresiaBadge(c.estado)
                const nombre    = esVenta ? nombreClienteVenta(c) : nombreClienteMembresia(c)
                const monto     = esVenta ? c.total : (c.precio_acordado ?? c.precio_pagado)
                const concepto  = esVenta ? `Venta #${c.id}` : (c.plan?.nombre ?? `Membresía #${c.id}`)
                return (
                  <tr key={`${c.tipo}-${c.id}`}>
                    <td>{formatFechaHora(c.creado_en)}</td>
                    <td>
                      <span className="text-muted" style={{
                        fontSize: '0.75rem', fontWeight: 600,
                        textTransform: 'uppercase', letterSpacing: '0.03em',
                      }}>
                        {esVenta ? 'POS' : 'Membresía'}
                      </span>
                    </td>
                    <td className="td-nombre">{nombre}</td>
                    <td>{concepto}</td>
                    <td className="num">${Number(monto).toFixed(2)}</td>
                    <td><span className={`badge ${clase}`}>{label}</span></td>
                    <td className="td-acciones">
                      <button className="btn btn-sm btn-outline" onClick={() => abrirDetalle(c)}>Ver detalle</button>
                      {esVenta && c.estado !== 'cancelada' && (
                        <button className="btn btn-sm btn-outline" onClick={() => abrirCostoExtra(c)}>+ Costo extra</button>
                      )}
                      <a
                        className="btn btn-sm btn-outline"
                        href={esVenta ? facturasAPI.ventaPdf(c.id) : facturasAPI.membresiaPdf(c.id)}
                        target="_blank" rel="noreferrer"
                      >
                        Factura
                      </a>
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      )}

      {/* ── Modal detalle ────────────────────────────────────────────────── */}
      {detalleModal && (
        <div className="modal-overlay" onClick={() => setDetalleModal(null)}>
          <div className="modal" ref={detalleModalRef} tabIndex={-1} onClick={e => e.stopPropagation()} style={{ maxWidth: 620 }}>
            <div className="modal-header">
              <h2>{detalleModal.tipo === 'venta' ? `Venta #${detalleModal.id}` : `Membresía #${detalleModal.id}`}</h2>
              <button className="modal-close" onClick={() => setDetalleModal(null)}>✕</button>
            </div>

            <div style={{ padding: '0 1.5rem 1.5rem' }}>
              {detalleModal.tipo === 'venta' ? (
                <>
                  <p className="text-muted" style={{ fontSize: '0.85rem', marginBottom: '0.9rem' }}>
                    {nombreClienteVenta(detalleModal)} · {formatFechaHora(detalleModal.creado_en)}
                  </p>

                  <ul style={{ listStyle: 'none', display: 'flex', flexDirection: 'column', gap: '0.3rem', marginBottom: '0.9rem' }}>
                    {detalleModal.items.map(i => (
                      <li key={i.id} style={{
                        display: 'flex', alignItems: 'center', gap: '0.75rem', fontSize: '0.85rem',
                        background: 'var(--color-surface-alt)', borderRadius: 6, padding: '0.4rem 0.6rem',
                      }}>
                        <span style={{ flex: 1 }}>{nombreItem(i)}</span>
                        <span className="text-muted">x{i.cantidad}</span>
                        <span className="num" style={{ fontWeight: 700 }}>${Number(i.subtotal).toFixed(2)}</span>
                      </li>
                    ))}
                  </ul>

                  <div style={{ display: 'flex', gap: '1.5rem', fontSize: '0.85rem', marginBottom: '0.9rem' }}>
                    <span>Subtotal: <strong className="num">${Number(detalleModal.subtotal).toFixed(2)}</strong></span>
                    <span>IVA ({detalleModal.porcentaje_iva}%): <strong className="num">${Number(detalleModal.monto_iva).toFixed(2)}</strong></span>
                    <span>Total: <strong className="num">${Number(detalleModal.total).toFixed(2)}</strong></span>
                  </div>

                  <h3 style={{ fontSize: '0.85rem', marginBottom: '0.5rem' }}>Pagos</h3>
                  {detalleModal.pagos.length === 0 ? (
                    <p className="text-muted" style={{ fontSize: '0.82rem' }}>Sin pagos registrados.</p>
                  ) : (
                    <ul style={{ listStyle: 'none', display: 'flex', flexDirection: 'column', gap: '0.3rem' }}>
                      {detalleModal.pagos.map(p => (
                        <li key={p.id} style={{
                          display: 'flex', alignItems: 'center', gap: '0.75rem', fontSize: '0.82rem',
                          background: 'var(--color-surface-alt)', borderRadius: 6, padding: '0.35rem 0.6rem',
                        }}>
                          <span className="text-muted">{formatFechaHora(p.fecha)}</span>
                          <span className="text-muted">{fmtMetodoPago(p.metodo)}</span>
                          <span className="num" style={{ marginLeft: 'auto', fontWeight: 700, color: 'var(--color-success-text)' }}>
                            +${Number(p.monto).toFixed(2)}
                          </span>
                        </li>
                      ))}
                    </ul>
                  )}

                  <div style={{ display: 'flex', gap: '0.6rem', marginTop: '1rem' }}>
                    <a className="btn btn-sm btn-outline" href={facturasAPI.ventaHtml(detalleModal.id)} target="_blank" rel="noreferrer">Ver factura</a>
                    <a className="btn btn-sm btn-outline" href={facturasAPI.ventaPdf(detalleModal.id)} target="_blank" rel="noreferrer">Descargar PDF</a>
                  </div>
                </>
              ) : (
                <>
                  <p className="text-muted" style={{ fontSize: '0.85rem', marginBottom: '0.9rem' }}>
                    {nombreClienteMembresia(detalleModal)} · {detalleModal.plan?.nombre ?? 'Plan eliminado'}
                  </p>

                  <div style={{ display: 'flex', gap: '1.5rem', fontSize: '0.85rem', marginBottom: '0.9rem' }}>
                    <span>Inicio: <strong>{formatFecha(detalleModal.fecha_inicio)}</strong></span>
                    {detalleModal.fecha_fin
                      ? <span>Vence: <strong>{formatFecha(detalleModal.fecha_fin)}</strong></span>
                      : <span>Clases: <strong>{detalleModal.clases_usadas}/{detalleModal.clases_total ?? '—'}</strong></span>}
                  </div>

                  <div style={{ display: 'flex', gap: '1.5rem', fontSize: '0.85rem', marginBottom: '0.9rem' }}>
                    <span>Precio: <strong className="num">${Number(detalleModal.precio_acordado ?? detalleModal.precio_pagado).toFixed(2)}</strong></span>
                    {detalleModal.saldo > 0 && (
                      <span style={{ color: 'var(--color-danger)' }}>Saldo: <strong className="num">${Number(detalleModal.saldo).toFixed(2)}</strong></span>
                    )}
                  </div>

                  <h3 style={{ fontSize: '0.85rem', marginBottom: '0.5rem' }}>Pagos</h3>
                  {cargandoPagosMem ? (
                    <p className="estado-msg">Cargando…</p>
                  ) : detalleModal.pagos.length === 0 ? (
                    <p className="text-muted" style={{ fontSize: '0.82rem' }}>Sin pagos registrados.</p>
                  ) : (
                    <ul style={{ listStyle: 'none', display: 'flex', flexDirection: 'column', gap: '0.3rem' }}>
                      {detalleModal.pagos.map(p => (
                        <li key={p.id} style={{
                          display: 'flex', alignItems: 'center', gap: '0.75rem', fontSize: '0.82rem',
                          background: 'var(--color-surface-alt)', borderRadius: 6, padding: '0.35rem 0.6rem',
                        }}>
                          <span className="text-muted">{formatFechaHora(p.fecha)}</span>
                          <span className="text-muted">{fmtMetodoPago(p.metodo)}</span>
                          <span className="num" style={{ marginLeft: 'auto', fontWeight: 700, color: 'var(--color-success-text)' }}>
                            +${Number(p.monto).toFixed(2)}
                          </span>
                        </li>
                      ))}
                    </ul>
                  )}

                  <div style={{ display: 'flex', gap: '0.6rem', marginTop: '1rem' }}>
                    <a className="btn btn-sm btn-outline" href={facturasAPI.membresiaPdf(detalleModal.id)} target="_blank" rel="noreferrer">Descargar PDF</a>
                  </div>
                </>
              )}
            </div>
          </div>
        </div>
      )}

      {/* ── Modal costo extra (solo ventas) ──────────────────────────────── */}
      {costoExtraModal && (
        <div className="modal-overlay" onClick={() => !guardandoCosto && setCostoExtraModal(null)}>
          <div className="modal" ref={costoExtraModalRef} tabIndex={-1} onClick={e => e.stopPropagation()}>
            <div className="modal-header">
              <h2>Añadir costo extra</h2>
              <button className="modal-close" onClick={() => setCostoExtraModal(null)}>✕</button>
            </div>

            <form className="modal-form" onSubmit={confirmarCostoExtra}>
              <p className="text-muted" style={{ fontSize: '0.85rem', margin: '0 0 0.5rem' }}>
                {nombreClienteVenta(costoExtraModal)}
              </p>

              <label>
                <span className="label-text">Descripción <span className="required">*</span></span>
                <input
                  type="text"
                  placeholder="Ej. reposición de candado, servicio especial..."
                  value={costoExtraForm.descripcion}
                  onChange={e => setCostoExtraForm(p => ({ ...p, descripcion: e.target.value }))}
                  autoFocus
                />
              </label>

              <label>
                <span className="label-text">Monto <span className="required">*</span></span>
                <input
                  type="number"
                  step="0.01"
                  min="0.01"
                  className="num"
                  value={costoExtraForm.monto}
                  onChange={e => setCostoExtraForm(p => ({ ...p, monto: e.target.value }))}
                />
              </label>

              <label>
                <span className="label-text">Observación</span>
                <textarea
                  rows={3}
                  placeholder="Opcional — contexto de este cargo"
                  value={costoExtraForm.notas}
                  onChange={e => setCostoExtraForm(p => ({ ...p, notas: e.target.value }))}
                />
              </label>

              {costoExtraError && <p className="mensaje-error">{costoExtraError}</p>}

              <div className="modal-footer">
                <button type="button" className="btn btn-outline" onClick={() => setCostoExtraModal(null)} disabled={guardandoCosto}>
                  Cancelar
                </button>
                <button type="submit" className="btn btn-primary" disabled={guardandoCosto}>
                  {guardandoCosto ? 'Guardando…' : 'Agregar cargo'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  )
}
