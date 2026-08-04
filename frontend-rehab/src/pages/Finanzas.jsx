import { useState, useEffect, useCallback } from 'react'
import { finanzasAPI } from '../services/api'
import { formatFecha, MESES } from '@shared/utils/fecha'
import { useMonthNavigator } from '@shared/hooks/useMonthNavigator'
import { useFocusTrap } from '@shared/hooks/useFocusTrap'
import '@shared/pages/Finanzas.css'

const FORM_VACIO = { categoria: '', descripcion: '', monto: '', es_fijo: false }

const CATEGORIAS_BASE = [
  'Arriendo', 'Servicios básicos', 'Transporte', 'Publicidad',
  'Empaque', 'Comisiones', 'Otros',
]

// ─── Componente ────────────────────────────────────────────────────────────────

export default function Finanzas() {
  const { mes, anio, esMesActual, retroceder, avanzar } = useMonthNavigator()

  // Datos
  const [gastos, setGastos]     = useState([])
  const [resumen, setResumen]   = useState(null)
  const [cargando, setCargando] = useState(true)
  const [error, setError]       = useState(null)

  // Filtro local de gastos
  const [filtroTipo, setFiltroTipo] = useState('todos')  // todos | fijo | variable

  // Modal gasto
  const [modal, setModal]           = useState(false)
  const [editandoId, setEditandoId] = useState(null)
  const [form, setForm]             = useState(FORM_VACIO)
  const [guardando, setGuardando]   = useState(false)
  const [formError, setFormError]   = useState(null)

  // Confirmación eliminar
  const [eliminarId, setEliminarId]     = useState(null)
  const [eliminando, setEliminando]     = useState(false)

  const modalRef         = useFocusTrap(!!modal)
  const eliminarModalRef = useFocusTrap(!!eliminarId)

  // ─── Carga ──────────────────────────────────────────────────────────────────

  const cargarTodo = useCallback(async () => {
    try {
      setCargando(true)
      setError(null)
      const [rGastos, rResumen] = await Promise.all([
        finanzasAPI.listarGastos(),
        finanzasAPI.resumen(mes, anio),
      ])
      setGastos(rGastos.data)
      setResumen(rResumen.data)
    } catch {
      setError('No se pudo conectar con el servidor.')
    } finally {
      setCargando(false)
    }
  }, [mes, anio])

  useEffect(() => { cargarTodo() }, [cargarTodo])

  // ─── Gastos filtrados ────────────────────────────────────────────────────────

  const gastosFiltrados = gastos.filter(g => {
    if (filtroTipo === 'fijo')     return g.es_fijo
    if (filtroTipo === 'variable') return !g.es_fijo
    return true
  })

  // ─── Modal ───────────────────────────────────────────────────────────────────

  function abrirCrear() {
    setForm(FORM_VACIO)
    setEditandoId(null)
    setFormError(null)
    setModal(true)
  }

  function abrirEditar(g) {
    setForm({
      categoria:   g.categoria,
      descripcion: g.descripcion ?? '',
      monto:       g.monto,
      es_fijo:     g.es_fijo,
    })
    setEditandoId(g.id)
    setFormError(null)
    setModal(true)
  }

  async function guardar(e) {
    e.preventDefault()
    if (!form.categoria.trim()) { setFormError('La categoría es obligatoria.'); return }
    const monto = parseFloat(form.monto)
    if (!monto || monto <= 0)   { setFormError('El monto debe ser mayor a 0.'); return }

    const payload = {
      categoria:   form.categoria.trim(),
      descripcion: form.descripcion.trim() || undefined,
      monto,
      es_fijo:     form.es_fijo,
    }

    try {
      setGuardando(true)
      setFormError(null)
      if (editandoId) {
        await finanzasAPI.actualizarGasto(editandoId, payload)
      } else {
        await finanzasAPI.crearGasto(payload)
      }
      setModal(false)
      await cargarTodo()
    } catch (err) {
      setFormError(err.response?.data?.detail ?? 'Error al guardar.')
    } finally {
      setGuardando(false)
    }
  }

  // ─── Eliminar ────────────────────────────────────────────────────────────────

  async function confirmarEliminar() {
    if (!eliminarId) return
    try {
      setEliminando(true)
      await finanzasAPI.eliminarGasto(eliminarId)
      setEliminarId(null)
      await cargarTodo()
    } finally {
      setEliminando(false)
    }
  }

  // ─── Render ──────────────────────────────────────────────────────────────────

  return (
    <div className="finanzas">

      {/* Header */}
      <div className="page-header">
        <h1>Finanzas</h1>
        <div className="mes-nav">
          <button className="mes-btn" onClick={retroceder}>‹</button>
          <span className="mes-label">{MESES[mes - 1]} {anio}</span>
          <button
            className={`mes-btn ${esMesActual ? 'mes-btn-disabled' : ''}`}
            onClick={avanzar}
            disabled={esMesActual}
          >›</button>
        </div>
      </div>

      {cargando && <p className="estado-msg">Cargando…</p>}
      {error    && <p className="estado-msg error">{error}</p>}

      {!cargando && !error && resumen && (
        <>
          {/* Resumen del mes */}
          <div className="resumen-panel">
            <h2 className="resumen-titulo">Resumen — {MESES[mes - 1]} {anio}</h2>
            <div className="resumen-grid">

              <div className="resumen-item">
                <span className="resumen-label">Ingresos</span>
                <span className="resumen-valor num positivo">${resumen.ingresos.toFixed(2)}</span>
              </div>

              <div className="resumen-item">
                <span className="resumen-label">Costo productos</span>
                <span className="resumen-valor num negativo">−${resumen.costo_ventas.toFixed(2)}</span>
              </div>

              <div className="resumen-item resumen-bruta">
                <span className="resumen-label">Ganancia bruta</span>
                <span className="resumen-valor num">${resumen.ganancia_bruta.toFixed(2)}</span>
              </div>

              <div className="resumen-divisor" />

              <div className="resumen-item">
                <span className="resumen-label">Gastos fijos</span>
                <span className="resumen-valor num negativo">−${resumen.gastos_fijos.toFixed(2)}</span>
                <span className="resumen-hint">siempre incluidos</span>
              </div>

              <div className="resumen-item">
                <span className="resumen-label">Gastos variables</span>
                <span className="resumen-valor num negativo">−${resumen.gastos_variables.toFixed(2)}</span>
                <span className="resumen-hint">del mes</span>
              </div>

              <div className={`resumen-item resumen-neta ${resumen.ganancia_neta >= 0 ? 'neta-positiva' : 'neta-negativa'}`}>
                <span className="resumen-label">Ganancia neta</span>
                <span className="resumen-valor num">
                  {resumen.ganancia_neta >= 0 ? '+' : ''}${resumen.ganancia_neta.toFixed(2)}
                </span>
              </div>

            </div>
          </div>

          {/* Sección gastos */}
          <div className="gastos-header">
            <div className="gastos-titulo-row">
              <h2>Gastos registrados</h2>
              <button className="btn-primario" onClick={abrirCrear}>+ Nuevo gasto</button>
            </div>
            <div className="filtro-pills">
              {[
                { value: 'todos',    label: 'Todos' },
                { value: 'fijo',     label: '📌 Fijos' },
                { value: 'variable', label: 'Variables' },
              ].map(f => (
                <button
                  key={f.value}
                  className={`pill ${filtroTipo === f.value ? 'pill-activo' : ''}`}
                  onClick={() => setFiltroTipo(f.value)}
                >
                  {f.label}
                  {f.value !== 'todos' && (
                    <span className="pill-count num">
                      {gastos.filter(g => f.value === 'fijo' ? g.es_fijo : !g.es_fijo).length}
                    </span>
                  )}
                </button>
              ))}
            </div>
          </div>

          {gastosFiltrados.length === 0 ? (
            <div className="estado-vacio">
              <span className="material-symbols-outlined vacio-icono">payments</span>
              <p>No hay gastos registrados.</p>
            </div>
          ) : (
            <ul className="gastos-lista">
              {gastosFiltrados.map(g => (
                <li key={g.id} className={`gasto-row ${g.es_fijo ? 'gasto-fijo' : ''}`}>
                  <div className="gasto-info">
                    <span className="gasto-categoria">{g.categoria}</span>
                    {g.descripcion && <span className="gasto-desc">{g.descripcion}</span>}
                  </div>
                  <div className="gasto-meta">
                    {g.es_fijo
                      ? <span className="gasto-badge-fijo">📌 Fijo</span>
                      : <span className="gasto-badge-var">Variable</span>
                    }
                    <span className="gasto-fecha">{formatFecha(g.fecha)}</span>
                  </div>
                  <span className="gasto-monto num">−${g.monto.toFixed(2)}</span>
                  <div className="gasto-acciones">
                    <button className="btn-sm-outline" onClick={() => abrirEditar(g)}>Editar</button>
                    <button className="btn-sm-danger"  onClick={() => setEliminarId(g.id)}>✕</button>
                  </div>
                </li>
              ))}
            </ul>
          )}
        </>
      )}

      {/* ── Modal gasto ─────────────────────────────────────────────────────── */}
      {modal && (
        <div className="modal-overlay" onClick={() => !guardando && setModal(false)}>
          <div className="modal" ref={modalRef} tabIndex={-1} onClick={e => e.stopPropagation()}>
            <div className="modal-header">
              <h2>{editandoId ? 'Editar gasto' : 'Nuevo gasto'}</h2>
            </div>

            <form onSubmit={guardar} className="gasto-form">

              <div className="form-group">
                <label><span className="label-text">Categoría <span className="required">*</span></span></label>
                <input
                  list="categorias-list"
                  placeholder="Ej: Arriendo, Transporte…"
                  value={form.categoria}
                  onChange={e => setForm(f => ({ ...f, categoria: e.target.value }))}
                  autoFocus
                />
                <datalist id="categorias-list">
                  {CATEGORIAS_BASE.map(c => <option key={c} value={c} />)}
                </datalist>
              </div>

              <div className="form-group">
                <label><span className="label-text">Descripción</span></label>
                <input
                  type="text"
                  placeholder="Opcional — detalle del gasto"
                  value={form.descripcion}
                  onChange={e => setForm(f => ({ ...f, descripcion: e.target.value }))}
                />
              </div>

              <div className="form-group">
                <label><span className="label-text">Monto <span className="required">*</span></span></label>
                <input
                  type="number"
                  step="0.01"
                  min="0.01"
                  className="num"
                  placeholder="0.00"
                  value={form.monto}
                  onChange={e => setForm(f => ({ ...f, monto: e.target.value }))}
                />
              </div>

              <label className="toggle-fijo">
                <input
                  type="checkbox"
                  checked={form.es_fijo}
                  onChange={e => setForm(f => ({ ...f, es_fijo: e.target.checked }))}
                />
                <span>
                  <strong>📌 Gasto fijo mensual</strong>
                  <small>Se incluye automáticamente en el resumen de todos los meses</small>
                </span>
              </label>

              {formError && <p className="form-error">{formError}</p>}

              <div className="modal-acciones">
                <button type="button" className="btn-secundario" onClick={() => setModal(false)} disabled={guardando}>
                  Cancelar
                </button>
                <button type="submit" className="btn-primario" disabled={guardando}>
                  {guardando ? 'Guardando…' : editandoId ? 'Guardar cambios' : 'Crear gasto'}
                </button>
              </div>

            </form>
          </div>
        </div>
      )}

      {/* ── Modal confirmar eliminar ─────────────────────────────────────────── */}
      {eliminarId && (
        <div className="modal-overlay" onClick={() => !eliminando && setEliminarId(null)}>
          <div className="modal modal-confirmar" ref={eliminarModalRef} tabIndex={-1} onClick={e => e.stopPropagation()}>
            <div className="confirmar-icono">🗑️</div>
            <h2>¿Eliminar este gasto?</h2>
            <p className="confirmar-aviso">Esta acción no se puede deshacer.</p>
            <div className="modal-acciones">
              <button className="btn-secundario" onClick={() => setEliminarId(null)} disabled={eliminando}>
                Cancelar
              </button>
              <button className="btn-danger" onClick={confirmarEliminar} disabled={eliminando}>
                {eliminando ? 'Eliminando…' : 'Sí, eliminar'}
              </button>
            </div>
          </div>
        </div>
      )}

    </div>
  )
}
