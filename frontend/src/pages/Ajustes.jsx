import { useState, useEffect } from 'react'
import { configuracionAPI, suscripcionesAPI } from '../services/api'
import { estadoSaasBadge, fmtPlanSaas, fmtTierSaas, fmtEstadoPagoSaas } from '@shared/utils/formato'
import { formatFecha, formatFechaHora } from '@shared/utils/fecha'
import '@shared/pages/Ajustes.css'
import '@shared/pages/Clientes.css'

const VACIO = { nombre: '', ruc: '', direccion: '', telefono: '', iva_default: 0 }
// opcion combina plan+tier en un solo <select> ("mensual::" para renovar el
// tier actual, "mensual::solo" para pedir el tier Solo) — se separa recién
// al armar el payload, en solicitarRenovacion.
const VACIO_SOLICITUD = { opcion: '', referencia: '', notas: '', comprobante: null }

export default function Ajustes({ onNombreActualizado }) {
  const [form, setForm]         = useState(VACIO)
  const [cargando, setCargando] = useState(true)
  const [guardando, setGuardando] = useState(false)
  const [guardado, setGuardado] = useState(false)
  const [error, setError]       = useState(null)

  useEffect(() => {
    configuracionAPI.obtener()
      .then(r => setForm({
        nombre:      r.data.nombre      ?? '',
        ruc:         r.data.ruc         ?? '',
        direccion:   r.data.direccion   ?? '',
        telefono:    r.data.telefono    ?? '',
        iva_default: r.data.iva_default ?? 0,
      }))
      .catch(() => setError('No se pudo cargar la configuración.'))
      .finally(() => setCargando(false))
  }, [])

  function handleChange(e) {
    const { name, value } = e.target
    setForm(f => ({ ...f, [name]: name === 'iva_default' ? parseFloat(value) || 0 : value }))
    setGuardado(false)
  }

  async function guardar(e) {
    e.preventDefault()
    try {
      setGuardando(true)
      setError(null)
      await configuracionAPI.actualizar(form)
      setGuardado(true)
      onNombreActualizado?.(form.nombre)
    } catch {
      setError('Error al guardar.')
    } finally {
      setGuardando(false)
    }
  }

  // ── Suscripción SaaS ────────────────────────────────────────────────────
  const [sus, setSus]                 = useState(null)   // /suscripciones/estado
  const [historialSus, setHistorialSus] = useState([])
  const [cargandoSus, setCargandoSus] = useState(true)
  const [formSus, setFormSus]         = useState(VACIO_SOLICITUD)
  const [enviandoSus, setEnviandoSus] = useState(false)
  const [errorSus, setErrorSus]       = useState(null)
  const [exitoSus, setExitoSus]       = useState(false)

  useEffect(() => {
    cargarSuscripcion()
  }, [])

  async function cargarSuscripcion() {
    try {
      setCargandoSus(true)
      const [estadoRes, historialRes] = await Promise.all([
        suscripcionesAPI.estado(),
        suscripcionesAPI.historial(),
      ])
      setSus(estadoRes.data)
      setHistorialSus(historialRes.data)
    } catch {
      setErrorSus('No se pudo cargar la suscripción.')
    } finally {
      setCargandoSus(false)
    }
  }

  function handleChangeSus(e) {
    const { name, value } = e.target
    setFormSus(f => ({ ...f, [name]: value }))
    setExitoSus(false)
  }

  function handleArchivoSus(e) {
    setFormSus(f => ({ ...f, comprobante: e.target.files[0] || null }))
    setExitoSus(false)
  }

  async function solicitarRenovacion(e) {
    e.preventDefault()
    if (!formSus.opcion)      return setErrorSus('Selecciona un plan.')
    if (!formSus.referencia)  return setErrorSus('Ingresa el número de la transferencia.')
    if (!formSus.comprobante) return setErrorSus('Sube la foto del comprobante de la transferencia.')

    const [plan, tier] = formSus.opcion.split('::')

    try {
      setEnviandoSus(true)
      setErrorSus(null)
      await suscripcionesAPI.solicitar({
        plan,
        tier: tier || undefined,
        referencia:  formSus.referencia,
        notas:       formSus.notas,
        comprobante: formSus.comprobante,
      })
      setFormSus(VACIO_SOLICITUD)
      setExitoSus(true)
      await cargarSuscripcion()
    } catch (err) {
      setErrorSus(err.response?.data?.detail ?? 'Error al enviar la solicitud.')
    } finally {
      setEnviandoSus(false)
    }
  }

  if (cargando) return <div className="ajustes"><p className="estado-msg">Cargando…</p></div>

  const badgeSus = sus ? estadoSaasBadge(sus.saas_estado) : null

  return (
    <div className="ajustes">
      <div className="page-header">
        <h1>Ajustes</h1>
      </div>

      {/* ── Suscripción ─────────────────────────────────────────── */}
      <div className="ajustes-seccion">
        <div className="ajustes-seccion-titulo">
          <span className="ajustes-icono">💳</span>
          Suscripción
        </div>

        {cargandoSus && <p className="estado-msg">Cargando…</p>}
        {!cargandoSus && !sus && errorSus && <p className="form-error">{errorSus}</p>}

        {!cargandoSus && sus && (
          <>
            <div className="sus-resumen">
              <span className={`badge ${badgeSus.clase}`}>{badgeSus.label}</span>
              <span className="sus-plan">{fmtPlanSaas(sus.saas_plan)}</span>
              {sus.saas_vence_en && (
                <span className="text-muted">vence el {formatFecha(sus.saas_vence_en)}</span>
              )}
              {!sus.saas_vence_en && sus.saas_trial_hasta && (
                <span className="text-muted">prueba hasta el {formatFecha(sus.saas_trial_hasta)}</span>
              )}
              {sus.dias_restantes !== null && (
                <span className="text-muted">({sus.dias_restantes} día{sus.dias_restantes === 1 ? '' : 's'})</span>
              )}
            </div>

            {sus.saas_estado === 'en_gracia' && (
              <p className="form-error">
                Tu suscripción venció y estás en período de gracia. Regulariza el pago antes de que
                se suspenda el acceso.
              </p>
            )}

            {sus.pago_pendiente ? (
              <p className="ajustes-desc">
                Ya tienes una solicitud de pago en revisión. El equipo la confirmará en 1-2 días hábiles.
              </p>
            ) : (
              <form className="sus-form" onSubmit={solicitarRenovacion}>
                <p className="ajustes-desc">Solicitar renovación por transferencia bancaria.</p>

                <div className="ajustes-grid">
                  <div className="form-group">
                    <label>
                      <span className="label-text">Plan <span className="required">*</span></span>
                      <select name="opcion" value={formSus.opcion} onChange={handleChangeSus} required>
                        <option value="">Selecciona un plan</option>
                        {sus.planes_disponibles.map(o => {
                          const valor = `${o.plan}::${o.tier ?? ''}`
                          const etiqueta = o.tier
                            ? `${fmtTierSaas(o.tier)} — ${fmtPlanSaas(o.plan)} — $${Number(o.precio).toFixed(2)} (${o.dias} días)`
                            : `${fmtPlanSaas(o.plan)} — $${Number(o.precio).toFixed(2)} (${o.dias} días)`
                          return <option key={valor} value={valor}>{etiqueta}</option>
                        })}
                      </select>
                    </label>
                  </div>

                  <div className="form-group">
                    <label>
                      <span className="label-text">N° de transferencia <span className="required">*</span></span>
                      <input
                        name="referencia"
                        value={formSus.referencia}
                        onChange={handleChangeSus}
                        placeholder="Ej: 000123456"
                        required
                      />
                    </label>
                  </div>

                  <div className="form-group form-group-full">
                    <label>
                      <span className="label-text">Notas</span>
                      <input
                        name="notas"
                        value={formSus.notas}
                        onChange={handleChangeSus}
                        placeholder="Opcional"
                      />
                    </label>
                  </div>

                  <div className="form-group form-group-full">
                    <label>
                      <span className="label-text">
                        Comprobante de la transferencia <span className="required">*</span>
                      </span>
                      <input type="file" accept="image/jpeg,image/png" onChange={handleArchivoSus} required />
                    </label>
                  </div>
                </div>

                {errorSus && <p className="form-error">{errorSus}</p>}

                <div className="ajustes-footer">
                  {exitoSus && <span className="ajustes-ok">✓ Solicitud enviada</span>}
                  <button type="submit" className="btn-primario" disabled={enviandoSus}>
                    {enviandoSus ? 'Enviando…' : 'Solicitar renovación'}
                  </button>
                </div>
              </form>
            )}

            {historialSus.length > 0 && (
              <div className="sus-historial">
                <div className="ajustes-seccion-titulo" style={{ fontSize: '0.78rem' }}>Historial de pagos</div>
                {historialSus.map(p => {
                  const badgePago = fmtEstadoPagoSaas(p.estado)
                  return (
                    <div key={p.id} className="sus-historial-item">
                      <span className={`badge ${badgePago.clase}`}>{badgePago.label}</span>
                      <span className="sus-plan">
                        {fmtPlanSaas(p.plan)}
                        {p.tier_solicitado && ` → ${fmtTierSaas(p.tier_solicitado)}`}
                      </span>
                      <span className="num">${Number(p.monto).toFixed(2)}</span>
                      <span className="text-muted">{formatFechaHora(p.solicitado_en)}</span>
                      {p.comprobante_url && (
                        <a href={p.comprobante_url} target="_blank" rel="noreferrer" className="sus-link">
                          Ver comprobante
                        </a>
                      )}
                      {p.estado === 'rechazado' && p.razon_rechazo && (
                        <span className="text-muted sus-razon">{p.razon_rechazo}</span>
                      )}
                    </div>
                  )
                })}
              </div>
            )}
          </>
        )}
      </div>

      <form className="ajustes-form" onSubmit={guardar}>

        {/* ── Datos del negocio ──────────────────────────────────── */}
        <div className="ajustes-seccion">
          <div className="ajustes-seccion-titulo">
            <span className="ajustes-icono">🏪</span>
            Datos del negocio
          </div>
          <p className="ajustes-desc">
            Aparecen en el encabezado y en el bloque Emisor de cada factura PDF.
          </p>

          <div className="ajustes-grid">
            <div className="form-group">
              <label>
                <span className="label-text">Nombre del negocio <span className="required">*</span></span>
                <input
                  name="nombre"
                  value={form.nombre}
                  onChange={handleChange}
                  placeholder="Ej: CrossFit Machala"
                  required
                  autoFocus
                />
              </label>
            </div>

            <div className="form-group">
              <label>
                <span className="label-text">RUC</span>
                <input
                  name="ruc"
                  value={form.ruc}
                  onChange={handleChange}
                  placeholder="0000000000001"
                  maxLength={13}
                />
              </label>
            </div>

            <div className="form-group form-group-full">
              <label>
                <span className="label-text">Dirección</span>
                <input
                  name="direccion"
                  value={form.direccion}
                  onChange={handleChange}
                  placeholder="Ej: Av. Principal 123, Machala, Ecuador"
                />
              </label>
            </div>

            <div className="form-group">
              <label>
                <span className="label-text">Teléfono</span>
                <input
                  name="telefono"
                  value={form.telefono}
                  onChange={handleChange}
                  placeholder="Ej: 0999 999 999"
                />
              </label>
            </div>
          </div>
        </div>

        {/* ── IVA ───────────────────────────────────────────────── */}
        <div className="ajustes-seccion">
          <div className="ajustes-seccion-titulo">
            <span className="ajustes-icono">🧾</span>
            IVA por defecto
          </div>
          <p className="ajustes-desc">
            El porcentaje que se sugiere en el POS al cobrar. Lo puedes cambiar por venta desde el POS.
            Ecuador usa 15 % actualmente; usa 0 si no cobras IVA.
          </p>

          <div className="ajustes-iva-row">
            <div className="form-group iva-group">
              <label>
                <span className="label-text">IVA %</span>
                <div className="iva-input-wrap">
                  <input
                    type="number"
                    name="iva_default"
                    value={form.iva_default}
                    onChange={handleChange}
                    min="0"
                    max="100"
                    step="0.1"
                    className="num"
                  />
                  <span className="iva-pct-label">%</span>
                </div>
              </label>
            </div>

            <div className="iva-presets">
              {[0, 5, 12, 15].map(pct => (
                <button
                  key={pct}
                  type="button"
                  className={`preset-btn ${form.iva_default === pct ? 'preset-activo' : ''}`}
                  onClick={() => { setForm(f => ({ ...f, iva_default: pct })); setGuardado(false) }}
                >
                  {pct}%
                </button>
              ))}
            </div>
          </div>
        </div>

        {/* ── Acciones ──────────────────────────────────────────── */}
        {error && <p className="form-error">{error}</p>}

        <div className="ajustes-footer">
          {guardado && <span className="ajustes-ok">✓ Guardado correctamente</span>}
          <button type="submit" className="btn-primario" disabled={guardando}>
            {guardando ? 'Guardando…' : 'Guardar ajustes'}
          </button>
        </div>

      </form>
    </div>
  )
}
