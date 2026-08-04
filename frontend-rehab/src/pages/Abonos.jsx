import { useState, useEffect, useCallback } from 'react'
import { abonosAPI, membresiasAPI, ventasAPI, deudasAPI } from '../services/api'
import { formatFecha } from '@shared/utils/fecha'
import { fmtMetodoPago } from '@shared/utils/formato'
import { useFocusTrap } from '@shared/hooks/useFocusTrap'
import '@shared/pages/Abonos.css'

function nombreCompleto(miembro) {
  if (!miembro) return 'Sin paciente'
  return [miembro.nombre, miembro.apellido].filter(Boolean).join(' ')
}

const FILTROS = [
  { value: 'todos',   label: 'Todos'    },
  { value: 'abono',   label: 'Abonos'   },
  { value: 'deudor',  label: 'Deudores' },
]

const PAGO_VACIO = { monto: '', metodo: 'efectivo', notas: '', comprobante: null }

function badgeDeuda(pagado) {
  return pagado === 0
    ? { label: 'Deudor', clase: 'badge badge-deudor' }
    : { label: 'Abono',  clase: 'badge badge-abono'  }
}

function badgeTipo(tipo) {
  return tipo === 'venta'
    ? { label: 'POS',       clase: 'badge badge-tipo-venta'     }
    : { label: 'Membresía', clase: 'badge badge-tipo-membresia' }
}

export default function Abonos() {
  const [registros, setRegistros] = useState([])
  const [cargando, setCargando]   = useState(true)
  const [error, setError]         = useState(null)
  const [filtro, setFiltro]       = useState('todos')
  const [busqueda, setBusqueda]   = useState('')

  const [pagoModal, setPagoModal] = useState(null)  // { id, tipo, saldo, nombre }
  const [pagoForm, setPagoForm]   = useState(PAGO_VACIO)
  const [pagando, setPagando]     = useState(false)
  const [pagoError, setPagoError] = useState(null)

  const [histModal, setHistModal]         = useState(null)
  const [cargandoHist, setCargandoHist]   = useState(false)

  const [eliminarModal, setEliminarModal] = useState(null)  // { id, nombre, total }
  const [eliminando, setEliminando]       = useState(false)

  const pagoModalRef     = useFocusTrap(!!pagoModal)
  const histModalRef     = useFocusTrap(!!histModal)
  const eliminarModalRef = useFocusTrap(!!eliminarModal)

  // ─── Carga ────────────────────────────────────────────────────────────────────

  const cargar = useCallback(async () => {
    try {
      setCargando(true)
      setError(null)
      const res = await deudasAPI.listar()
      setRegistros(res.data)
    } catch {
      setError('No se pudo conectar con el servidor.')
    } finally {
      setCargando(false)
    }
  }, [])

  useEffect(() => { cargar() }, [cargar])

  // ─── Filtro ───────────────────────────────────────────────────────────────────

  const filtrados = registros.filter(r => {
    const matchFiltro =
      filtro === 'abono'  ? r.pagado > 0   :
      filtro === 'deudor' ? r.pagado === 0  :
      true
    const nombre = nombreCompleto(r.miembro).toLowerCase()
    const matchBusqueda = busqueda === '' || nombre.includes(busqueda.toLowerCase())
    return matchFiltro && matchBusqueda
  })

  const totalPendiente = filtrados.reduce((acc, r) => acc + r.pendiente, 0)

  // ─── Registrar pago ───────────────────────────────────────────────────────────

  function abrirPago(r) {
    setPagoModal({ id: r.id, tipo: r.tipo, saldo: r.pendiente, nombre: nombreCompleto(r.miembro) })
    setPagoForm({ ...PAGO_VACIO, monto: r.pendiente.toFixed(2) })
    setPagoError(null)
  }

  function handleArchivoPago(e) {
    setPagoForm(p => ({ ...p, comprobante: e.target.files[0] || null }))
  }

  async function confirmarPago(e) {
    e.preventDefault()
    const monto = parseFloat(pagoForm.monto)
    if (!monto || monto <= 0) { setPagoError('Ingresa un monto válido.'); return }
    if (monto > pagoModal.saldo + 0.001) {
      setPagoError(`El monto supera el saldo pendiente ($${pagoModal.saldo.toFixed(2)})`)
      return
    }
    try {
      setPagando(true)
      setPagoError(null)
      if (pagoModal.tipo === 'venta') {
        await abonosAPI.pagar(pagoModal.id, { monto, metodo: pagoForm.metodo, notas: pagoForm.notas || undefined })
      } else {
        await membresiasAPI.registrarPago(pagoModal.id, {
          monto, metodo: pagoForm.metodo, notas: pagoForm.notas || undefined, comprobante: pagoForm.comprobante,
        })
      }
      setPagoModal(null)
      await cargar()
    } catch (err) {
      setPagoError(err.response?.data?.detail ?? 'Error al registrar el pago.')
    } finally {
      setPagando(false)
    }
  }

  // ─── Eliminar venta (solo tipo "venta") ───────────────────────────────────────

  function abrirEliminar(r) {
    setEliminarModal({ id: r.id, nombre: nombreCompleto(r.miembro), total: r.total })
  }

  async function confirmarEliminar() {
    if (!eliminarModal) return
    try {
      setEliminando(true)
      await ventasAPI.eliminar(eliminarModal.id)
      setEliminarModal(null)
      await cargar()
    } catch (err) {
      alert(err.response?.data?.detail ?? 'No se pudo eliminar la venta.')
    } finally {
      setEliminando(false)
    }
  }

  // ─── Historial ────────────────────────────────────────────────────────────────

  async function abrirHistorial(r) {
    setHistModal({
      nombre:      nombreCompleto(r.miembro),
      descripcion: r.descripcion,
      tipo:        r.tipo,
      total:       r.total,
      pagado:      r.pagado,
      pendiente:   r.pendiente,
      pagos:       [],
    })
    setCargandoHist(true)
    try {
      let pagos
      if (r.tipo === 'venta') {
        const res = await abonosAPI.detalle(r.id)
        pagos = res.data.pagos ?? []
      } else {
        const res = await membresiasAPI.listarPagos(r.id)
        pagos = res.data ?? []
      }
      setHistModal(prev => ({ ...prev, pagos }))
    } finally {
      setCargandoHist(false)
    }
  }

  // ─── Render ───────────────────────────────────────────────────────────────────

  return (
    <div className="abonos">

      <div className="page-header">
        <h1>Abonos</h1>
        {!cargando && (
          <div className="abonos-resumen">
            <span className="resumen-label">Saldo pendiente total</span>
            <span className="resumen-monto num">${totalPendiente.toFixed(2)}</span>
          </div>
        )}
      </div>

      <div className="abonos-controles">
        <input
          className="input-busqueda"
          type="text"
          placeholder="Buscar por cliente…"
          value={busqueda}
          onChange={e => setBusqueda(e.target.value)}
        />
        <div className="filtro-pills">
          {FILTROS.map(f => (
            <button
              key={f.value}
              className={`pill ${filtro === f.value ? 'pill-activo' : ''}`}
              onClick={() => setFiltro(f.value)}
            >
              {f.label}
              {f.value !== 'todos' && (
                <span className="pill-count num">
                  {registros.filter(r =>
                    f.value === 'deudor' ? r.pagado === 0 : r.pagado > 0
                  ).length}
                </span>
              )}
            </button>
          ))}
        </div>
      </div>

      {cargando && <p className="estado-msg">Cargando…</p>}
      {error    && <p className="estado-msg error">{error}</p>}

      {!cargando && !error && filtrados.length === 0 && (
        <div className="estado-vacio">
          <span className="material-symbols-outlined vacio-icono">check_circle</span>
          <p>No hay saldos pendientes</p>
        </div>
      )}

      {!cargando && !error && filtrados.length > 0 && (
        <ul className="abonos-lista">
          {filtrados.map(r => {
            const bDeuda = badgeDeuda(r.pagado)
            const bTipo  = badgeTipo(r.tipo)
            const pct    = Math.min(100, r.total > 0 ? (r.pagado / r.total) * 100 : 0)
            const nombre = nombreCompleto(r.miembro)
            return (
              <li key={`${r.tipo}-${r.id}`} className={`abono-card ${r.pagado === 0 ? 'card-deudor' : 'card-abono'}`}>

                <div className="card-top">
                  <div className="card-info">
                    <span className="card-nombre">{nombre}</span>
                    <span className="card-producto">{r.descripcion}</span>
                  </div>
                  <div className="card-top-right">
                    <span className={bTipo.clase}>{bTipo.label}</span>
                    <span className={bDeuda.clase}>{bDeuda.label}</span>
                    {r.tipo === 'venta' && (
                      <button
                        className="btn-eliminar-card"
                        title="Eliminar esta venta"
                        onClick={() => abrirEliminar(r)}
                      >✕</button>
                    )}
                  </div>
                </div>

                <div className="progreso-wrap">
                  <div className="progreso-barra">
                    <div className="progreso-fill" style={{ width: `${pct}%` }} />
                  </div>
                  <span className="progreso-pct num">{Math.round(pct)}%</span>
                </div>

                <div className="card-montos">
                  <div className="monto-item">
                    <span className="monto-label">Total</span>
                    <span className="monto-val num">${r.total.toFixed(2)}</span>
                  </div>
                  <div className="monto-item">
                    <span className="monto-label">Pagado</span>
                    <span className="monto-val num pagado">${r.pagado.toFixed(2)}</span>
                  </div>
                  <div className="monto-item monto-saldo">
                    <span className="monto-label">Saldo</span>
                    <span className="monto-val num saldo">${r.pendiente.toFixed(2)}</span>
                  </div>
                </div>

                <div className="card-footer">
                  <span className="card-fecha">{formatFecha(r.fecha)}</span>
                  <div className="card-acciones">
                    <button className="btn-historial" onClick={() => abrirHistorial(r)}>
                      Ver pagos
                    </button>
                    <button className="btn-pagar" onClick={() => abrirPago(r)}>
                      Registrar pago
                    </button>
                  </div>
                </div>

              </li>
            )
          })}
        </ul>
      )}

      {/* ── Modal registrar pago ─────────────────────────────────────────────── */}
      {pagoModal && (
        <div className="modal-overlay" onClick={() => !pagando && setPagoModal(null)}>
          <div className="modal" ref={pagoModalRef} tabIndex={-1} onClick={e => e.stopPropagation()}>
            <div className="modal-header">
              <h2>Registrar pago</h2>
              <span className="modal-cliente">{pagoModal.nombre}</span>
            </div>

            <div className="modal-saldo-info">
              Saldo pendiente: <strong className="num">${pagoModal.saldo.toFixed(2)}</strong>
            </div>

            <form onSubmit={confirmarPago} className="pago-form">
              <div className="form-group">
                <label>
                  <span className="label-text">Monto <span className="required">*</span></span>
                </label>
                <input
                  type="number"
                  step="0.01"
                  min="0.01"
                  max={pagoModal.saldo}
                  className="num"
                  value={pagoForm.monto}
                  onChange={e => setPagoForm(p => ({ ...p, monto: e.target.value }))}
                  autoFocus
                />
              </div>

              <div className="form-group">
                <label><span className="label-text">Método de pago</span></label>
                <div className="metodo-toggle">
                  {['efectivo', 'transferencia'].map(m => (
                    <button
                      key={m}
                      type="button"
                      className={`metodo-btn ${pagoForm.metodo === m ? 'metodo-activo' : ''}`}
                      onClick={() => setPagoForm(p => ({ ...p, metodo: m }))}
                    >
                      {m === 'efectivo' ? '💵 Efectivo' : '📲 Transferencia'}
                    </button>
                  ))}
                </div>
              </div>

              <div className="form-group">
                <label><span className="label-text">Notas</span></label>
                <input
                  type="text"
                  placeholder="Opcional"
                  value={pagoForm.notas}
                  onChange={e => setPagoForm(p => ({ ...p, notas: e.target.value }))}
                />
              </div>

              {pagoModal.tipo !== 'venta' && (
                <div className="form-group">
                  <label><span className="label-text">Comprobante de pago (opcional, jpg o png)</span></label>
                  <input type="file" accept="image/jpeg,image/png" onChange={handleArchivoPago} />
                </div>
              )}

              {pagoError && <p className="form-error">{pagoError}</p>}

              <div className="modal-acciones">
                <button type="button" className="btn-secundario" onClick={() => setPagoModal(null)} disabled={pagando}>
                  Cancelar
                </button>
                <button type="submit" className="btn-primario" disabled={pagando}>
                  {pagando ? 'Registrando…' : 'Confirmar pago'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* ── Modal historial de pagos ─────────────────────────────────────────── */}
      {histModal && (
        <div className="modal-overlay" onClick={() => setHistModal(null)}>
          <div className="modal modal-historial" ref={histModalRef} tabIndex={-1} onClick={e => e.stopPropagation()}>
            <div className="modal-header">
              <h2>Historial de pagos</h2>
              <span className="modal-cliente">{histModal.nombre}</span>
            </div>

            <div className="hist-resumen">
              <div className="hist-stat">
                <span>Total</span>
                <strong className="num">${histModal.total.toFixed(2)}</strong>
              </div>
              <div className="hist-stat">
                <span>Ya pagado</span>
                <strong className="num pagado">${histModal.pagado.toFixed(2)}</strong>
              </div>
              <div className="hist-stat">
                <span>Saldo</span>
                <strong className="num saldo">${histModal.pendiente.toFixed(2)}</strong>
              </div>
            </div>

            <div className="hist-concepto">
              <span className="hist-concepto-label">Concepto</span>
              <span className="hist-concepto-valor">{histModal.descripcion}</span>
            </div>

            <h3 className="hist-titulo-pagos">Pagos realizados</h3>

            {cargandoHist && <p className="estado-msg">Cargando…</p>}

            {!cargandoHist && histModal.pagos.length === 0 && (
              <p className="estado-msg">Ningún pago registrado todavía.</p>
            )}

            {!cargandoHist && histModal.pagos.length > 0 && (
              <ul className="hist-pagos-lista">
                {histModal.pagos.map(p => (
                  <li key={p.id} className="hist-pago-row">
                    <span className="hist-pago-fecha">{formatFecha(p.fecha)}</span>
                    <span className="hist-pago-metodo">{fmtMetodoPago(p.metodo)}</span>
                    {p.notas && <span className="hist-pago-notas">{p.notas}</span>}
                    {p.comprobante_url && (
                      <a className="hist-pago-comprobante" href={p.comprobante_url} target="_blank" rel="noreferrer">
                        Ver comprobante
                      </a>
                    )}
                    <span className="hist-pago-monto num">+${p.monto.toFixed(2)}</span>
                  </li>
                ))}
              </ul>
            )}

            <div className="modal-acciones">
              <button className="btn-primario" onClick={() => setHistModal(null)}>Cerrar</button>
            </div>
          </div>
        </div>
      )}

      {/* ── Modal confirmar eliminación ──────────────────────────────────────── */}
      {eliminarModal && (
        <div className="modal-overlay" onClick={() => !eliminando && setEliminarModal(null)}>
          <div className="modal modal-eliminar" ref={eliminarModalRef} tabIndex={-1} onClick={e => e.stopPropagation()}>
            <div className="eliminar-icono">🗑️</div>
            <h2>¿Eliminar esta venta?</h2>
            <p className="eliminar-desc">
              <strong>{eliminarModal.nombre}</strong> — total{' '}
              <span className="num">${eliminarModal.total.toFixed(2)}</span>
            </p>
            <p className="eliminar-aviso">
              Esta acción no se puede deshacer. El stock de los productos
              se restaurará automáticamente.
            </p>
            <div className="modal-acciones">
              <button
                className="btn-secundario"
                onClick={() => setEliminarModal(null)}
                disabled={eliminando}
              >
                Cancelar
              </button>
              <button
                className="btn-danger"
                onClick={confirmarEliminar}
                disabled={eliminando}
              >
                {eliminando ? 'Eliminando…' : 'Sí, eliminar'}
              </button>
            </div>
          </div>
        </div>
      )}

    </div>
  )
}
