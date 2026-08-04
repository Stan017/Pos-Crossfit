import { useState, useEffect, useCallback } from 'react'
import { suscripcionesAdminAPI } from '../services/api'
import { fmtPlanSaas, formatFechaHora } from '../utils/formato'
import './Clientes.css'
import './PagosPendientes.css'

const NOMBRE_KEY = 'darkcross_admin_nombre'

export default function PagosPendientes() {
  const [pagos, setPagos]       = useState([])
  const [cargando, setCargando] = useState(true)
  const [error, setError]       = useState(null)
  const [procesando, setProcesando] = useState(null)  // pago.id en curso

  const [confirmarId, setConfirmarId] = useState(null)
  const [nombreConfirma, setNombreConfirma] = useState(localStorage.getItem(NOMBRE_KEY) || '')

  const [rechazarId, setRechazarId] = useState(null)
  const [razonRechazo, setRazonRechazo] = useState('')

  const cargar = useCallback(async () => {
    try {
      setCargando(true)
      setError(null)
      const res = await suscripcionesAdminAPI.pagosPendientes()
      setPagos(res.data)
    } catch {
      setError('No se pudo conectar con el servidor.')
    } finally {
      setCargando(false)
    }
  }, [])

  useEffect(() => { cargar() }, [cargar])

  function abrirConfirmar(pago) {
    setRechazarId(null)
    setConfirmarId(pago.id)
  }

  function abrirRechazar(pago) {
    setConfirmarId(null)
    setRazonRechazo('')
    setRechazarId(pago.id)
  }

  async function confirmar(pago) {
    if (!nombreConfirma.trim()) return alert('Ingresa tu nombre para confirmar el pago.')
    localStorage.setItem(NOMBRE_KEY, nombreConfirma.trim())

    setProcesando(pago.id)
    try {
      await suscripcionesAdminAPI.confirmarPago(pago.gym_id, {
        pago_saas_id: pago.id,
        confirmado_por: nombreConfirma.trim(),
      })
      setConfirmarId(null)
      await cargar()
    } catch (err) {
      alert(err.response?.data?.detail ?? 'No se pudo confirmar el pago.')
    } finally {
      setProcesando(null)
    }
  }

  async function rechazar(pago) {
    setProcesando(pago.id)
    try {
      await suscripcionesAdminAPI.rechazarPago(pago.gym_id, {
        pago_saas_id: pago.id,
        razon_rechazo: razonRechazo.trim() || null,
      })
      setRechazarId(null)
      await cargar()
    } catch (err) {
      alert(err.response?.data?.detail ?? 'No se pudo rechazar el pago.')
    } finally {
      setProcesando(null)
    }
  }

  return (
    <div className="page">
      <div className="page-header">
        <h1>Pagos pendientes</h1>
        <span className="total-label">{pagos.length} pendiente{pagos.length === 1 ? '' : 's'}</span>
      </div>

      {error && <p className="mensaje-error">{error}</p>}

      {cargando ? (
        <p className="cargando">Cargando...</p>
      ) : pagos.length === 0 ? (
        <p className="vacio">No hay pagos esperando confirmación.</p>
      ) : (
        <div className="pagos-lista">
          {pagos.map(p => (
            <div key={p.id} className="pago-card">
              <div className="pago-comprobante">
                {p.comprobante_url ? (
                  <a href={p.comprobante_url} target="_blank" rel="noreferrer">
                    <img src={p.comprobante_url} alt={`Comprobante de ${p.gym_nombre}`} />
                  </a>
                ) : (
                  <div className="pago-sin-comprobante">Sin comprobante</div>
                )}
              </div>

              <div className="pago-info">
                <div className="pago-info-header">
                  <span className="td-nombre">{p.gym_nombre}</span>
                  <span className="num pago-monto">${Number(p.monto).toFixed(2)}</span>
                </div>
                <div className="text-muted">{fmtPlanSaas(p.plan)} · ref. {p.referencia || '—'}</div>
                {p.notas && <div className="text-muted pago-notas">&quot;{p.notas}&quot;</div>}
                <div className="text-muted">{formatFechaHora(p.solicitado_en)}</div>

                {confirmarId === p.id ? (
                  <div className="pago-accion-form">
                    <input
                      value={nombreConfirma}
                      onChange={e => setNombreConfirma(e.target.value)}
                      placeholder="Tu nombre"
                      autoFocus
                    />
                    <button className="btn btn-sm btn-primary" onClick={() => confirmar(p)} disabled={procesando === p.id}>
                      {procesando === p.id ? 'Confirmando…' : 'Confirmar pago'}
                    </button>
                    <button className="btn btn-sm btn-outline" onClick={() => setConfirmarId(null)}>Cancelar</button>
                  </div>
                ) : rechazarId === p.id ? (
                  <div className="pago-accion-form">
                    <input
                      value={razonRechazo}
                      onChange={e => setRazonRechazo(e.target.value)}
                      placeholder="Razón del rechazo (opcional)"
                      autoFocus
                    />
                    <button className="btn btn-sm btn-danger" onClick={() => rechazar(p)} disabled={procesando === p.id}>
                      {procesando === p.id ? 'Rechazando…' : 'Rechazar pago'}
                    </button>
                    <button className="btn btn-sm btn-outline" onClick={() => setRechazarId(null)}>Cancelar</button>
                  </div>
                ) : (
                  <div className="td-acciones pago-acciones">
                    <button className="btn btn-sm btn-primary" onClick={() => abrirConfirmar(p)}>Confirmar</button>
                    <button className="btn btn-sm btn-danger" onClick={() => abrirRechazar(p)}>Rechazar</button>
                  </div>
                )}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
