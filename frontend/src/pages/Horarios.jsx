import { useState, useEffect } from 'react'
import { horariosAPI, miembrosAPI, instructoresAPI } from '../services/api'
import { formatFecha, parseFechaLocal, hoyLocal } from '@shared/utils/fecha'
import { useFocusTrap } from '@shared/hooks/useFocusTrap'
import '@shared/pages/Clientes.css'

// ── Utilidades de fecha ───────────────────────────────────────────────────────

const DIAS_NOMBRES = ['Dom', 'Lun', 'Mar', 'Mié', 'Jue', 'Vie', 'Sáb']
const MESES = ['ene','feb','mar','abr','may','jun','jul','ago','sep','oct','nov','dic']

function lunesDe(isoDate) {
  const d = parseFechaLocal(isoDate)
  const dow = d.getDay()
  const diff = dow === 0 ? -6 : 1 - dow
  d.setDate(d.getDate() + diff)
  return d.toISOString().slice(0, 10)
}

function addDays(isoDate, n) {
  const d = parseFechaLocal(isoDate)
  d.setDate(d.getDate() + n)
  return d.toISOString().slice(0, 10)
}

function diasDeSemana(lunes) {
  return Array.from({ length: 6 }, (_, i) => addDays(lunes, i))
}

// "Gestionar clases" no necesita el historial completo del gym, solo lo
// reciente/próximo — acota la query en vez de traer todas las clases desde
// el día uno (crece sin límite con el tiempo).
const GESTION_DIAS_ATRAS    = 30
const GESTION_DIAS_ADELANTE = 90

function labelSemana(lunes) {
  const sabado = addDays(lunes, 5)
  const dl = parseFechaLocal(lunes)
  const ds = parseFechaLocal(sabado)
  const mes = MESES[ds.getMonth()]
  if (dl.getMonth() === ds.getMonth())
    return `${dl.getDate()} – ${ds.getDate()} ${mes} ${ds.getFullYear()}`
  return `${dl.getDate()} ${MESES[dl.getMonth()]} – ${ds.getDate()} ${mes} ${ds.getFullYear()}`
}

function labelDia(iso) {
  const d = parseFechaLocal(iso)
  return { nombre: DIAS_NOMBRES[d.getDay()], numero: d.getDate() }
}

function esHoy(iso) {
  return iso === hoyLocal()
}

function formatHora(str) {
  if (!str) return '—'
  return str.slice(0, 5)
}

// ── Helpers de estado ─────────────────────────────────────────────────────────

function badgeEstado(estado) {
  const map = {
    programada: { color: '#1976d2', bg: '#e3f0fb' },
    en_curso:   { color: '#2e7d32', bg: '#e8f5e9' },
    completada: { color: '#555',    bg: '#f0f0f0' },
    cancelada:  { color: '#c62828', bg: '#fdecea' },
  }
  const s = map[estado] || { color: '#555', bg: '#f0f0f0' }
  return (
    <span style={{
      fontSize: '0.68rem', fontWeight: 600, padding: '1px 7px',
      borderRadius: 99, background: s.bg, color: s.color,
    }}>
      {estado}
    </span>
  )
}

// ── Constantes del formulario ─────────────────────────────────────────────────

const DIAS_SEMANA = [
  { valor: 1, label: 'Lun' },
  { valor: 2, label: 'Mar' },
  { valor: 3, label: 'Mié' },
  { valor: 4, label: 'Jue' },
  { valor: 5, label: 'Vie' },
  { valor: 6, label: 'Sáb' },
  { valor: 0, label: 'Dom' },
]

const TIPOS_CLASE = [
  'WOD', 'Open Gym', 'Weightlifting', 'Gymnastics',
  'Mobility', 'CrossFit Kids', 'Endurance', 'Foundations',
]

function formVacio() {
  return {
    fecha_inicio: hoyLocal(), fecha_fin: hoyLocal(), hora_inicio: '06:00', hora_fin: '07:00',
    nombre: '', instructor_id: '', capacidad: 20, notas: '',
    dias: [1, 2, 3, 4, 5],
  }
}

// ── Grilla por hora ────────────────────────────────────────────────────────────

const HORA_GRID_INICIO = 6   // 6:00
const HORA_GRID_FIN    = 21  // 21:00
const HORAS_GRID = Array.from(
  { length: HORA_GRID_FIN - HORA_GRID_INICIO },
  (_, i) => HORA_GRID_INICIO + i
)

function minutosDeHora(horaStr) {
  const [h, m] = horaStr.split(':').map(Number)
  return h * 60 + m
}

// Agrupa las clases del día en "islas" de horarios que se solapan y asigna un
// carril a cada una dentro de su isla (mismo criterio que Google Calendar),
// para que dos clases a la misma hora se vean lado a lado en vez de tapadas.
function calcularCarriles(clasesDelDia) {
  const ordenadas = [...clasesDelDia].sort((a, b) => a.hora_inicio.localeCompare(b.hora_inicio))
  const resultado = []
  let isla = []
  let finMaximoIsla = null

  function cerrarIsla() {
    if (isla.length === 0) return
    const finPorCarril = []
    const inicioIndice = resultado.length
    for (const clase of isla) {
      const inicio = minutosDeHora(clase.hora_inicio)
      let carril = finPorCarril.findIndex(fin => fin <= inicio)
      if (carril === -1) {
        carril = finPorCarril.length
        finPorCarril.push(0)
      }
      finPorCarril[carril] = minutosDeHora(clase.hora_fin)
      resultado.push({ clase, carril })
    }
    for (let i = inicioIndice; i < resultado.length; i++) {
      resultado[i].totalCarriles = finPorCarril.length
    }
    isla = []
    finMaximoIsla = null
  }

  for (const clase of ordenadas) {
    const inicio = minutosDeHora(clase.hora_inicio)
    if (finMaximoIsla !== null && inicio >= finMaximoIsla) cerrarIsla()
    isla.push(clase)
    const fin = minutosDeHora(clase.hora_fin)
    finMaximoIsla = finMaximoIsla === null ? fin : Math.max(finMaximoIsla, fin)
  }
  cerrarIsla()

  return resultado
}

function clamp(valor, min, max) {
  return Math.min(max, Math.max(min, valor))
}

// Una clase que no pisa nada del rango visible (termina antes de que arranque
// la grilla, o arranca después de que termina) no tiene ningún minuto que
// mostrar ahí — se lista igual en "Gestionar clases", pero no en la grilla.
function claseFueraDeGrid(clase) {
  const desdeGrid = HORA_GRID_INICIO * 60
  const hastaGrid = HORA_GRID_FIN * 60
  return minutosDeHora(clase.hora_fin) <= desdeGrid || minutosDeHora(clase.hora_inicio) >= hastaGrid
}

// Posición y tamaño del bloque dentro de la columna del día, en porcentaje del
// rango horario visible (HORA_GRID_INICIO–HORA_GRID_FIN). Una clase que arranca
// antes de las 6:00 o termina después de las 21:00 se recorta simétricamente
// contra los dos bordes — solo se ve la porción que realmente cae dentro del
// horario visible, nunca una astilla falsa pegada a un borde que no le
// corresponde. (Las que no pisan la grilla para nada las filtra claseFueraDeGrid
// antes de llegar acá.)
function estiloBloque(clase, carril, totalCarriles) {
  const desdeGrid = HORA_GRID_INICIO * 60
  const hastaGrid = HORA_GRID_FIN * 60
  const totalGrid = hastaGrid - desdeGrid

  const inicio = minutosDeHora(clase.hora_inicio)
  const fin    = minutosDeHora(clase.hora_fin)

  const top    = clamp(((inicio - desdeGrid) / totalGrid) * 100, 0, 100)
  const bottom = clamp(((fin    - desdeGrid) / totalGrid) * 100, 0, 100)
  const alto   = Math.max(bottom - top, 1.5)

  const ancho     = 100 / totalCarriles
  const izquierda = carril * ancho

  return {
    top:    `${top}%`,
    height: `${alto}%`,
    left:   `${izquierda}%`,
    width:  `${ancho}%`,
  }
}

// ── Componente principal ──────────────────────────────────────────────────────

export default function Horarios() {
  const [semanaInicio,     setSemanaInicio]     = useState(lunesDe(hoyLocal()))
  const [clases,           setClases]           = useState([])
  const [cargando,         setCargando]         = useState(true)
  const [error,            setError]            = useState(null)
  const [claseActiva,      setClaseActiva]      = useState(null)
  const [reservaciones,    setReservaciones]    = useState([])
  const [cargandoRes,      setCargandoRes]      = useState(false)
  const [modalNueva,       setModalNueva]       = useState(false)
  const [form,             setForm]             = useState(formVacio)
  const [guardando,        setGuardando]        = useState(false)
  const [errForm,          setErrForm]          = useState(null)
  const [instructores,     setInstructores]     = useState([])
  const [busqueda,         setBusqueda]         = useState('')
  const [sugerencias,      setSugerencias]      = useState([])
  const [buscandoMiembro,  setBuscandoMiembro]  = useState(false)
  const [agregando,        setAgregando]        = useState(false)
  const [modalGestion,     setModalGestion]     = useState(false)
  const [todasClases,      setTodasClases]      = useState([])
  const [cargandoTodas,    setCargandoTodas]    = useState(false)
  const modalNuevaRef   = useFocusTrap(modalNueva)
  const modalGestionRef = useFocusTrap(modalGestion)
  const [busquedaGestion,  setBusquedaGestion]  = useState('')

  const semanaFin  = addDays(semanaInicio, 5)
  const dias       = diasDeSemana(semanaInicio)

  // ── Cargar clases de la semana ───────────────────────────────────────────────

  useEffect(() => { cargarClases() }, [semanaInicio])

  useEffect(() => {
    instructoresAPI.listar({ activo: true })
      .then(r => setInstructores(r.data))
      .catch(() => setInstructores([]))
  }, [])

  async function cargarClases() {
    try {
      setCargando(true)
      setError(null)
      const res = await horariosAPI.listarClases({ desde: semanaInicio, hasta: semanaFin })
      setClases(res.data)
      if (claseActiva) {
        const actualizada = res.data.find(c => c.id === claseActiva.id)
        setClaseActiva(actualizada || null)
      }
    } catch {
      setError('No se pudieron cargar las clases.')
    } finally {
      setCargando(false)
    }
  }

  function clasesDeDia(iso) {
    return clases
      .filter(c => c.fecha === iso)
      .sort((a, b) => a.hora_inicio.localeCompare(b.hora_inicio))
  }

  // ── Navegación de semana ─────────────────────────────────────────────────────

  function prevSemana() {
    setSemanaInicio(s => addDays(s, -7))
    setClaseActiva(null)
  }

  function nextSemana() {
    setSemanaInicio(s => addDays(s, 7))
    setClaseActiva(null)
  }

  function irAHoy() {
    setSemanaInicio(lunesDe(hoyLocal()))
    setClaseActiva(null)
  }

  // ── Reservaciones ────────────────────────────────────────────────────────────

  async function seleccionarClase(clase) {
    setClaseActiva(clase)
    setBusqueda('')
    setSugerencias([])
    try {
      setCargandoRes(true)
      const res = await horariosAPI.listarReservaciones(clase.id)
      setReservaciones(res.data)
    } catch {
      setReservaciones([])
    } finally {
      setCargandoRes(false)
    }
  }

  // ── Crear clase ──────────────────────────────────────────────────────────────

  function abrirModal() {
    setForm(formVacio())
    setErrForm(null)
    setModalNueva(true)
  }

  async function crearClase() {
    if (!form.nombre.trim()) {
      setErrForm('El nombre de la clase es obligatorio.')
      return
    }
    if (form.fecha_fin < form.fecha_inicio) {
      setErrForm('La fecha fin no puede ser anterior a la fecha inicio.')
      return
    }
    if (form.hora_fin <= form.hora_inicio) {
      setErrForm('La hora de fin debe ser posterior a la hora de inicio.')
      return
    }
    const fechas = []
    const cur = parseFechaLocal(form.fecha_inicio)
    const fin = parseFechaLocal(form.fecha_fin)
    while (cur <= fin) {
      if (form.dias.includes(cur.getDay()))
        fechas.push(cur.toISOString().slice(0, 10))
      cur.setDate(cur.getDate() + 1)
    }
    if (fechas.length === 0) {
      setErrForm('Ninguna fecha del rango cae en los días seleccionados.')
      return
    }

    setGuardando(true)
    setErrForm(null)

    // allSettled, no all: con recurrencia (varias fechas = varios requests
    // independientes) un fallo a mitad de camino no debe perderse el rastro de
    // cuáles ya se crearon. Promise.all corta apenas la primera falla y no dice
    // nada de las que sí terminaron — el usuario, creyendo que no se guardó
    // nada, reintentaba el rango completo y duplicaba las que ya habían quedado.
    const resultados = await Promise.allSettled(fechas.map(f => horariosAPI.crearClase({
      fecha:         f,
      hora_inicio:   form.hora_inicio,
      hora_fin:      form.hora_fin,
      nombre:        form.nombre.trim(),
      instructor_id: form.instructor_id || null,
      capacidad:     Number(form.capacidad),
      notas:         form.notas.trim() || null,
    })))
    setGuardando(false)

    const fallidas  = resultados.filter(r => r.status === 'rejected')
    const exitosas  = resultados.length - fallidas.length

    if (fallidas.length === 0) {
      setModalNueva(false)
      cargarClases()
      return
    }

    if (exitosas === 0) {
      // Nada se creó — el modal queda abierto con el form intacto, como antes.
      setErrForm(fallidas[0].reason?.response?.data?.detail ?? 'Error al crear la clase.')
      return
    }

    // Fallo parcial: algo sí quedó guardado. Cerramos el modal en vez de dejar
    // el mismo rango cargado — reabrir con "+ Nueva clase" resetea el form, así
    // que no queda la tentación de tocar "Crear clase" de nuevo con el rango
    // completo y duplicar lo que ya se creó.
    setModalNueva(false)
    cargarClases()
    alert(`Se crearon ${exitosas} de ${fechas.length} clases. ${fallidas.length} fallaron — revisá el calendario antes de crear las que falten.`)
  }

  // ── Cancelar / eliminar clase ────────────────────────────────────────────────

  async function cancelarClase(clase) {
    if (!confirm(`¿Cancelar la clase "${clase.nombre}"?`)) return
    try {
      await horariosAPI.cancelarClase(clase.id)
      if (claseActiva?.id === clase.id) setClaseActiva(null)
      cargarClases()
      if (modalGestion) cargarTodasClases()
    } catch (err) {
      alert(err.response?.data?.detail ?? 'Error al cancelar.')
    }
  }

  async function eliminarClase(clase) {
    if (!confirm(`¿Eliminar permanentemente "${clase.nombre}"?\nSe borrarán también las reservaciones asociadas. Esta acción no se puede deshacer.`)) return
    try {
      await horariosAPI.eliminarClase(clase.id)
      if (claseActiva?.id === clase.id) setClaseActiva(null)
      cargarClases()
      if (modalGestion) cargarTodasClases()
    } catch (err) {
      alert(err.response?.data?.detail ?? 'Error al eliminar.')
    }
  }

  // ── Gestionar clases (todas, sin importar la semana visible) ────────────────

  async function cargarTodasClases() {
    try {
      setCargandoTodas(true)
      const res = await horariosAPI.listarClases({
        desde: addDays(hoyLocal(), -GESTION_DIAS_ATRAS),
        hasta: addDays(hoyLocal(), GESTION_DIAS_ADELANTE),
      })
      setTodasClases(res.data)
    } catch {
      setTodasClases([])
    } finally {
      setCargandoTodas(false)
    }
  }

  function abrirModalGestion() {
    setBusquedaGestion('')
    setModalGestion(true)
    cargarTodasClases()
  }

  // ── Buscar miembro para reservar ─────────────────────────────────────────────

  useEffect(() => {
    if (!busqueda.trim()) { setSugerencias([]); return }
    let ignore = false
    const t = setTimeout(async () => {
      try {
        setBuscandoMiembro(true)
        const res = await miembrosAPI.listar({ q: busqueda, activo: true })
        if (!ignore) setSugerencias(res.data.slice(0, 6))
      } catch {
        if (!ignore) setSugerencias([])
      } finally {
        if (!ignore) setBuscandoMiembro(false)
      }
    }, 250)
    return () => { ignore = true; clearTimeout(t) }
  }, [busqueda])

  async function reservarMiembro(miembro) {
    if (!claseActiva) return
    try {
      setAgregando(true)
      await horariosAPI.reservar(claseActiva.id, { miembro_id: miembro.id })
      setBusqueda('')
      setSugerencias([])
      const res = await horariosAPI.listarReservaciones(claseActiva.id)
      setReservaciones(res.data)
      cargarClases()
    } catch (err) {
      alert(err.response?.data?.detail ?? 'Error al reservar.')
    } finally {
      setAgregando(false)
    }
  }

  async function cambiarEstadoReservacion(id, estado) {
    try {
      await horariosAPI.actualizarReservacion(id, { estado })
      const res = await horariosAPI.listarReservaciones(claseActiva.id)
      setReservaciones(res.data)
    } catch (err) {
      alert(err.response?.data?.detail ?? 'Error al actualizar reservación.')
    }
  }

  // ── Render ───────────────────────────────────────────────────────────────────

  return (
    <div className="page clientes">

      {/* ── Encabezado ──────────────────────────────────────────────────────── */}
      <div className="page-header">
        <h1>Horarios</h1>
        <div style={{ display: 'flex', gap: '0.75rem', alignItems: 'center' }}>
          <div className="semana-nav">
            <button className="semana-nav-btn" onClick={prevSemana}>‹</button>
            <span className="semana-label">{labelSemana(semanaInicio)}</span>
            <button className="semana-nav-btn" onClick={nextSemana}>›</button>
            <button className="semana-hoy-btn" onClick={irAHoy}>Hoy</button>
          </div>
          <button className="btn btn-outline" onClick={abrirModalGestion}>Gestionar clases</button>
          <button className="btn btn-primary" onClick={abrirModal}>+ Nueva clase</button>
        </div>
      </div>

      {/* ── Contenido ───────────────────────────────────────────────────────── */}
      <div style={{ display: 'grid', gridTemplateColumns: claseActiva ? '1fr 360px' : '1fr', gap: '1.25rem', alignItems: 'start' }}>

        {/* ── Plantilla semanal ──────────────────────────────────────────── */}
        <div>
          {cargando ? (
            <p className="cargando">Cargando...</p>
          ) : error ? (
            <p className="estado-msg error">{error}</p>
          ) : (
            <div className="horario-grid-wrap">
              {/*
                Header y cuerpo son hijos directos de UNA sola grilla (no dos
                grids separados) para que las columnas de los días queden
                garantizadamente alineadas — con dos grids independientes el
                cálculo de ancho de cada uno puede redondear distinto (zoom
                fraccional, scrollbar) y las columnas se desalinean.
              */}
              <div className="horario-grid">
                <div className="horario-hora-gutter" />
                {dias.map(iso => {
                  const { nombre, numero } = labelDia(iso)
                  const esDiaHoy = esHoy(iso)
                  return (
                    <div key={iso} className={`horario-dia-header${esDiaHoy ? ' horario-dia-header-hoy' : ''}`}>
                      <span className="horario-dia-nombre">{nombre}</span>
                      <span className={`horario-dia-numero${esDiaHoy ? ' horario-dia-numero-hoy' : ''}`}>
                        {numero}
                      </span>
                    </div>
                  )
                })}

                <div className="horario-horas-col">
                  {HORAS_GRID.map(h => (
                    <div key={h} className="horario-hora-marca">{h}:00</div>
                  ))}
                </div>

                {dias.map(iso => {
                  const esDiaHoy = esHoy(iso)
                  // Filtra ANTES de calcularCarriles: una clase fuera de la grilla no
                  // debe competir por carril con las que sí son (parcialmente) visibles.
                  const conCarriles = calcularCarriles(clasesDeDia(iso).filter(c => !claseFueraDeGrid(c)))
                  return (
                    <div
                      key={iso}
                      className={`horario-dia-col${esDiaHoy ? ' horario-dia-col-hoy' : ''}`}
                      style={{ height: `calc(var(--horario-alto-hora) * ${HORAS_GRID.length})` }}
                    >
                      {/*
                        Filas reales (mismo elemento que .horario-hora-marca),
                        no un background-image — así el redondeo de subpíxel
                        con zoom fraccional es idéntico en las 7 columnas.
                      */}
                      {HORAS_GRID.map(h => (
                        <div key={h} className="horario-hora-fila" />
                      ))}
                      {conCarriles.map(({ clase, carril, totalCarriles }) => (
                        <div
                          key={clase.id}
                          className={`horario-clase-bloque${clase.estado === 'cancelada' ? ' cancelada' : ''}${claseActiva?.id === clase.id ? ' activa' : ''}`}
                          style={estiloBloque(clase, carril, totalCarriles)}
                          onClick={() => clase.estado !== 'cancelada' && seleccionarClase(clase)}
                          title={`${clase.nombre} · ${formatHora(clase.hora_inicio)}–${formatHora(clase.hora_fin)}${clase.instructor ? ' · ' + clase.instructor.nombre : ''}`}
                        >
                          <div className="horario-clase-bloque-hora">
                            {formatHora(clase.hora_inicio)}–{formatHora(clase.hora_fin)}
                          </div>
                          <div className="horario-clase-bloque-nombre">{clase.nombre}</div>
                          {clase.instructor && (
                            <div className="horario-clase-bloque-coach">{clase.instructor.nombre}</div>
                          )}
                          <div className="horario-clase-bloque-cupos">
                            {clase.reservados}/{clase.capacidad}
                          </div>
                        </div>
                      ))}
                    </div>
                  )
                })}
              </div>
            </div>
          )}
        </div>

        {/* ── Panel de reservaciones ──────────────────────────────────────── */}
        {claseActiva && (
          <div style={{
            background: 'var(--color-surface)',
            borderRadius: 12,
            border: '1px solid var(--color-border)',
            padding: '1.25rem',
            boxShadow: '0 2px 8px rgba(0,0,0,0.06)',
          }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '1rem' }}>
              <div>
                <div style={{ fontWeight: 700, fontSize: '1rem' }}>{claseActiva.nombre}</div>
                <div className="text-muted" style={{ fontSize: '0.8rem' }}>
                  {formatHora(claseActiva.hora_inicio)} – {formatHora(claseActiva.hora_fin)}
                  {claseActiva.instructor && <> · {claseActiva.instructor.nombre}</>}
                </div>
                <div className="text-muted" style={{ fontSize: '0.8rem', marginTop: 2 }}>
                  {claseActiva.reservados}/{claseActiva.capacidad} cupos
                </div>
              </div>
              <button
                onClick={() => setClaseActiva(null)}
                style={{ background: 'none', border: 'none', cursor: 'pointer', color: '#aaa', fontSize: '1.2rem', lineHeight: 1 }}
              >✕</button>
            </div>

            {/* Buscar miembro */}
            <div style={{ position: 'relative', marginBottom: '1rem' }}>
              <input
                type="text"
                placeholder="Agregar reserva — buscar miembro..."
                value={busqueda}
                onChange={e => setBusqueda(e.target.value)}
                className="input-busqueda"
                style={{ width: '100%', boxSizing: 'border-box' }}
              />
              {buscandoMiembro && <p style={{ fontSize: '0.8rem', color: '#aaa', margin: '4px 0 0' }}>Buscando...</p>}
              {sugerencias.length > 0 && (
                <ul className="checkin-sugerencias" style={{ position: 'absolute', zIndex: 10, width: '100%' }}>
                  {sugerencias.map(m => (
                    <li key={m.id} onClick={() => !agregando && reservarMiembro(m)}>
                      <strong>{m.nombre} {m.apellido}</strong>
                      {m.cedula && <span className="sug-detalle"> · {m.cedula}</span>}
                    </li>
                  ))}
                </ul>
              )}
            </div>

            {/* Lista de reservaciones */}
            {cargandoRes ? (
              <p className="cargando" style={{ fontSize: '0.85rem' }}>Cargando...</p>
            ) : reservaciones.length === 0 ? (
              <p style={{ color: '#aaa', fontSize: '0.85rem', textAlign: 'center', padding: '1.5rem 0' }}>
                Sin reservas aún.
              </p>
            ) : (
              <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
                {reservaciones.map(r => (
                  <div key={r.id} style={{
                    display: 'flex', alignItems: 'center', gap: '0.5rem',
                    padding: '0.5rem 0.75rem', borderRadius: 8,
                    background: r.estado === 'no_show' ? '#fff8f8' : r.estado === 'cancelada' ? '#f5f5f5' : '#f8fffe',
                    opacity: r.estado !== 'confirmada' ? 0.65 : 1,
                  }}>
                    <div style={{ flex: 1, fontSize: '0.85rem' }}>
                      <strong>{r.miembro?.nombre} {r.miembro?.apellido}</strong>
                    </div>
                    {r.estado === 'confirmada' && (
                      <div style={{ display: 'flex', gap: '0.35rem' }}>
                        <button
                          className="btn btn-sm btn-outline"
                          style={{ fontSize: '0.7rem', padding: '2px 8px' }}
                          onClick={() => cambiarEstadoReservacion(r.id, 'no_show')}
                        >No show</button>
                        <button
                          className="btn btn-sm btn-outline"
                          style={{ fontSize: '0.7rem', padding: '2px 8px', color: '#c62828', borderColor: '#c62828' }}
                          onClick={() => cambiarEstadoReservacion(r.id, 'cancelada')}
                        >✕</button>
                      </div>
                    )}
                    {r.estado !== 'confirmada' && (
                      <span style={{ fontSize: '0.72rem', color: r.estado === 'no_show' ? '#e53935' : '#aaa' }}>
                        {r.estado}
                      </span>
                    )}
                  </div>
                ))}
              </div>
            )}
          </div>
        )}
      </div>

      {/* ── Modal nueva clase ────────────────────────────────────────────────── */}
      {modalNueva && (
        <div className="modal-overlay" onClick={() => setModalNueva(false)}>
          <div className="modal" ref={modalNuevaRef} tabIndex={-1} onClick={e => e.stopPropagation()} style={{ maxWidth: 460 }}>
            <div className="modal-header">
              <h2>Nueva clase</h2>
              <button className="modal-close" onClick={() => setModalNueva(false)}>✕</button>
            </div>
            <div className="modal-form">
              <label>
                <span className="label-text">Tipo de clase</span>
                <select value={form.nombre} onChange={e => setForm(f => ({ ...f, nombre: e.target.value }))}>
                  <option value="">— Seleccionar tipo —</option>
                  {TIPOS_CLASE.map(t => <option key={t} value={t}>{t}</option>)}
                </select>
              </label>
              <label>
                <span className="label-text">Instructor</span>
                <select
                  value={form.instructor_id}
                  onChange={e => setForm(f => ({ ...f, instructor_id: e.target.value }))}
                >
                  <option value="">— Sin instructor —</option>
                  {instructores.map(i => <option key={i.id} value={i.id}>{i.nombre}</option>)}
                </select>
              </label>
              <div className="form-row">
                <label>
                  <span className="label-text">Desde</span>
                  <input type="date" value={form.fecha_inicio}
                    onChange={e => setForm(f => ({ ...f, fecha_inicio: e.target.value }))} />
                </label>
                <label>
                  <span className="label-text">Hasta</span>
                  <input type="date" value={form.fecha_fin}
                    onChange={e => setForm(f => ({ ...f, fecha_fin: e.target.value }))} />
                </label>
              </div>
              <div>
                <span className="label-text" style={{ display: 'block', marginBottom: '0.5rem' }}>Días</span>
                <div style={{ display: 'flex', gap: '0.4rem', flexWrap: 'wrap' }}>
                  {DIAS_SEMANA.map(d => {
                    const activo = form.dias.includes(d.valor)
                    return (
                      <button
                        key={d.valor}
                        type="button"
                        onClick={() => setForm(f => ({
                          ...f,
                          dias: activo
                            ? f.dias.filter(x => x !== d.valor)
                            : [...f.dias, d.valor],
                        }))}
                        style={{
                          padding: '0.3rem 0.7rem', borderRadius: 99,
                          border: `1px solid ${activo ? 'var(--color-primary)' : 'var(--color-border)'}`,
                          background: activo ? 'var(--color-primary)' : 'transparent',
                          color: activo ? '#fff' : 'var(--color-text-muted)',
                          fontSize: '0.8rem', fontWeight: 600, cursor: 'pointer',
                        }}
                      >{d.label}</button>
                    )
                  })}
                </div>
              </div>
              <div className="form-row">
                <label>
                  <span className="label-text">Hora inicio</span>
                  <input type="time" value={form.hora_inicio}
                    onChange={e => setForm(f => ({ ...f, hora_inicio: e.target.value }))} />
                </label>
                <label>
                  <span className="label-text">Hora fin</span>
                  <input type="time" value={form.hora_fin}
                    onChange={e => setForm(f => ({ ...f, hora_fin: e.target.value }))} />
                </label>
              </div>
              <label>
                <span className="label-text">Capacidad máxima</span>
                <input type="number" min="1" value={form.capacidad}
                  onChange={e => setForm(f => ({ ...f, capacidad: e.target.value }))} />
              </label>
              <label>
                <span className="label-text">Notas (opcional)</span>
                <textarea rows={2} value={form.notas}
                  onChange={e => setForm(f => ({ ...f, notas: e.target.value }))} />
              </label>
              {errForm && <p className="estado-msg error" style={{ margin: 0 }}>{errForm}</p>}
            </div>
            <div className="modal-footer">
              <button className="btn btn-outline" onClick={() => setModalNueva(false)}>Cancelar</button>
              <button className="btn btn-primary" onClick={crearClase} disabled={guardando}>
                {guardando ? 'Guardando...' : 'Crear clase'}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ── Modal gestionar clases ──────────────────────────────────────────── */}
      {modalGestion && (
        <div className="modal-overlay" onClick={() => setModalGestion(false)}>
          <div className="modal" ref={modalGestionRef} tabIndex={-1} onClick={e => e.stopPropagation()} style={{ maxWidth: 760 }}>
            <div className="modal-header">
              <h2>Gestionar clases</h2>
              <button className="modal-close" onClick={() => setModalGestion(false)}>✕</button>
            </div>
            <div style={{ padding: '0 1.5rem' }}>
              <input
                type="text"
                className="input-busqueda"
                style={{ width: '100%', boxSizing: 'border-box' }}
                placeholder="Buscar por nombre, instructor o fecha..."
                value={busquedaGestion}
                onChange={e => setBusquedaGestion(e.target.value)}
              />
              <p style={{ fontSize: '0.8rem', opacity: 0.65, margin: '0.4rem 0 0' }}>
                Muestra clases de los últimos {GESTION_DIAS_ATRAS} días y los próximos {GESTION_DIAS_ADELANTE}.
              </p>
            </div>
            <div className="tabla-wrapper" style={{ padding: '1rem 1.5rem 1.5rem' }}>
              {cargandoTodas ? (
                <p className="cargando">Cargando...</p>
              ) : (() => {
                const busq = busquedaGestion.trim().toLowerCase()
                const filtradas = todasClases.filter(c => (
                  !busq ||
                  c.nombre.toLowerCase().includes(busq) ||
                  (c.instructor?.nombre || '').toLowerCase().includes(busq) ||
                  c.fecha.includes(busq)
                ))
                if (filtradas.length === 0) {
                  return <p className="vacio">No hay clases que coincidan.</p>
                }
                return (
                  <table className="tabla">
                    <thead>
                      <tr>
                        <th>Fecha</th>
                        <th>Hora</th>
                        <th>Clase</th>
                        <th>Instructor</th>
                        <th>Cupos</th>
                        <th>Asistencias</th>
                        <th>Estado</th>
                        <th></th>
                      </tr>
                    </thead>
                    <tbody>
                      {filtradas.map(c => {
                        const tieneAsistencias = c.asistencias > 0
                        return (
                          <tr key={c.id}>
                            <td>{formatFecha(c.fecha)}</td>
                            <td>{formatHora(c.hora_inicio)}–{formatHora(c.hora_fin)}</td>
                            <td className="td-nombre">{c.nombre}</td>
                            <td>{c.instructor?.nombre || '—'}</td>
                            <td>{c.reservados}/{c.capacidad}</td>
                            <td>{c.asistencias}</td>
                            <td>{badgeEstado(c.estado)}</td>
                            <td>
                              <div style={{ display: 'flex', gap: '0.35rem', justifyContent: 'flex-end' }}>
                                {c.estado !== 'cancelada' && (
                                  <button
                                    className="horario-accion-btn cancelar"
                                    onClick={() => cancelarClase(c)}
                                    title="Cancelar clase"
                                  >✕ Cancelar</button>
                                )}
                                <button
                                  className="horario-accion-btn eliminar"
                                  onClick={() => eliminarClase(c)}
                                  disabled={tieneAsistencias}
                                  title={tieneAsistencias
                                    ? `No se puede eliminar: tiene ${c.asistencias} asistencia${c.asistencias !== 1 ? 's' : ''} registrada${c.asistencias !== 1 ? 's' : ''}. Cancelala en su lugar.`
                                    : 'Eliminar permanentemente'}
                                >🗑 Eliminar</button>
                              </div>
                            </td>
                          </tr>
                        )
                      })}
                    </tbody>
                  </table>
                )
              })()}
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
