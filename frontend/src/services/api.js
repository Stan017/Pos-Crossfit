import axios from 'axios'

const BASE = import.meta.env.VITE_API_URL ?? '/api'

// ── Axios instance ────────────────────────────────────────────────────────────
// La sesión vive en cookies httpOnly — el navegador las maneja solo.
// withCredentials: true para que viajen incluso si el request no es
// estrictamente same-origin (ej. si VITE_API_URL apunta a otro puerto/host).

const api = axios.create({
  baseURL: BASE,
  headers: { 'Content-Type': 'application/json' },
  withCredentials: true,
})

// El default de arriba (application/json) rompe cualquier request con
// FormData: axios ve que el Content-Type ya dice json y en vez de mandar el
// FormData tal cual, lo serializa como JSON string (ver
// axios/lib/defaults/index.js, hasJSONContentType) — el backend espera
// Form(...)/multipart en esos endpoints (comprobantes, fotos), así que
// terminaba viendo TODOS los campos como "Field required". Bug real,
// encontrado el 31/07/2026 al crear una membresía por primera vez en un
// navegador real (el build nunca lo iba a atrapar, es un problema de
// runtime). Este interceptor saca el Content-Type forzado solo cuando el
// body es FormData — el browser pone el multipart/boundary correcto solo.
api.interceptors.request.use(config => {
  if (config.data instanceof FormData) {
    delete config.headers['Content-Type']
  }
  return config
})

// ── Response interceptor: refresh on 401 ─────────────────────────────────────
// Si el refresh también falla, no hay sesión (o ya expiró) — se lo avisamos a
// App.jsx para que muestre el Login. Nada de window.location.href: eso forzaba
// una recarga completa de página, y si la causa del 401 era simplemente "nunca
// hubo sesión" (visita nueva), la recarga volvía a pedir /auth/me, volvía a
// fallar, volvía a recargar — loop infinito.

let refreshing = false
let queue = []
let onSessionExpired = null

export function setSessionExpiredHandler(fn) {
  onSessionExpired = fn
}

function flushQueue(error) {
  queue.forEach(({ resolve, reject }) => error ? reject(error) : resolve())
  queue = []
}

api.interceptors.response.use(
  res => res,
  async err => {
    const original = err.config
    if (err.response?.status !== 401 || original._retry) return Promise.reject(err)

    // Se marca ANTES de encolar, no solo para el líder que dispara el refresh:
    // si el request reintentado vuelve a dar 401 (sesión realmente muerta, no
    // solo una carrera con el refresh), tiene que rechazarse acá arriba en vez
    // de re-entrar y disparar otro ciclo de refresh.
    original._retry = true

    if (refreshing) {
      return new Promise((resolve, reject) => {
        queue.push({ resolve: () => resolve(api(original)), reject })
      })
    }

    refreshing = true

    try {
      await axios.post(`${BASE}/auth/refresh`, {}, { withCredentials: true })
      flushQueue(null)
      return api(original)
    } catch (refreshErr) {
      flushQueue(refreshErr)
      if (onSessionExpired) onSessionExpired()
      return Promise.reject(refreshErr)
    } finally {
      refreshing = false
    }
  }
)

// ── Auth ──────────────────────────────────────────────────────────────────────

export const authAPI = {
  login:       (data) => api.post('/auth/login', data),
  logout:      ()     => api.post('/auth/logout'),
  registerGym: (data) => api.post('/auth/register-gym', data),
  me:          ()     => api.get('/auth/me'),
}

// ── Miembros ──────────────────────────────────────────────────────────────────

export const miembrosAPI = {
  listar:     (params = {}) => api.get('/miembros/', { params }),
  obtener:    (id)          => api.get(`/miembros/${id}`),
  crear:      (data)        => api.post('/miembros/', data),
  actualizar: (id, data)    => api.put(`/miembros/${id}`, data),
  reactivar:  (id)          => api.patch(`/miembros/${id}/reactivar`),
  desactivar: (id)          => api.delete(`/miembros/${id}`),
}

// ── Planes ────────────────────────────────────────────────────────────────────

export const planesAPI = {
  listar:     ()         => api.get('/planes/'),
  listarTodos:()         => api.get('/planes/todos'),
  obtener:    (id)       => api.get(`/planes/${id}`),
  crear:      (data)     => api.post('/planes/', data),
  actualizar: (id, data) => api.patch(`/planes/${id}`, data),
  desactivar: (id)       => api.delete(`/planes/${id}`),
}

// ── Membresías ────────────────────────────────────────────────────────────────
// crear/renovar/registrarPago van como multipart: los tres pueden llevar un
// comprobante (foto jpg/png) además de los datos del pago, en un solo request.

function aFormData(data) {
  const form = new FormData()
  Object.entries(data).forEach(([key, value]) => {
    if (value !== null && value !== undefined && value !== '') form.append(key, value)
  })
  return form
}

export const membresiasAPI = {
  listar:         (params = {}) => api.get('/membresias/', { params }),
  alertas:        ()            => api.get('/membresias/alertas'),
  crear:          (data)        => api.post('/membresias/', aFormData(data)),
  renovar:        (id, data)    => api.patch(`/membresias/${id}/renovar`, aFormData(data)),
  listarPagos:    (id)          => api.get(`/membresias/${id}/pagos`),
  historialMiembro: (miembroId) => api.get(`/membresias/historial/${miembroId}`),
  registrarPago:  (id, data)    => api.post(`/membresias/${id}/pagos`, aFormData(data)),
  saldo:          (id)          => api.get(`/membresias/${id}/saldo`),
  eliminar:       (id)          => api.delete(`/membresias/${id}`),
  editarAsistencias: (id, clases_usadas) => api.patch(`/membresias/${id}/asistencias`, { clases_usadas }),
}

// ── Check-in ──────────────────────────────────────────────────────────────────

export const checkinAPI = {
  registrar: (data)       => api.post('/checkin/', data),
  listar:    (params = {})=> api.get('/checkin/', { params }),
}

// ── Usuarios (staff) ──────────────────────────────────────────────────────────

export const usuariosAPI = {
  listar:     ()         => api.get('/usuarios/'),
  obtener:    (id)       => api.get(`/usuarios/${id}`),
  crear:      (data)     => api.post('/usuarios/', data),
  actualizar: (id, data) => api.patch(`/usuarios/${id}`, data),
  eliminar:   (id)       => api.delete(`/usuarios/${id}`),
}

// ── Suscripción SaaS ──────────────────────────────────────────────────────────

export const suscripcionesAPI = {
  estado:    ()     => api.get('/suscripciones/estado'),
  historial: ()     => api.get('/suscripciones/historial'),
  solicitar: (data) => api.post('/suscripciones/solicitar', aFormData(data)),
}

// ── Productos e inventario ────────────────────────────────────────────────────

export const productosAPI = {
  listar:      (q = '')   => api.get(`/productos/?q=${q}`),
  obtener:     (id)       => api.get(`/productos/${id}`),
  crear:       (data)     => api.post('/productos/', data),
  actualizar:  (id, data) => api.patch(`/productos/${id}`, data),
  eliminar:    (id)       => api.delete(`/productos/${id}`),
  categorias:  ()         => api.get('/productos/categorias'),
  subirImagen: (id, file) => {
    const form = new FormData()
    form.append('file', file)
    return api.post(`/productos/${id}/imagen`, form)
  },
}

export const inventarioAPI = {
  listar:    (q = '')   => api.get(`/inventario/?q=${q}`),
  stockBajo: (limite=3) => api.get(`/inventario/stock-bajo?limite=${limite}`),
}

// ── Ventas (POS) ──────────────────────────────────────────────────────────────

export const ventasAPI = {
  listar:           (params = {}) => api.get('/ventas/', { params }),
  obtener:          (id)          => api.get(`/ventas/${id}`),
  crear:            (data)        => api.post('/ventas/', data),
  actualizar:       (id, data)    => api.patch(`/ventas/${id}`, data),
  actualizarItems:  (id, data)    => api.patch(`/ventas/${id}/items`, data),
  agregarCostoExtra:(id, data)    => api.post(`/ventas/${id}/costo-extra`, data),
  eliminar:         (id)          => api.delete(`/ventas/${id}`),
}

// ── Abonos (pagos parciales POS) ──────────────────────────────────────────────

export const abonosAPI = {
  listar:  ()              => api.get('/abonos/'),
  detalle: (ventaId)       => api.get(`/abonos/${ventaId}`),
  pagar:   (ventaId, data) => api.post(`/abonos/${ventaId}/pagar`, data),
}

// ── Deudas (vista unificada: ventas + membresías con saldo pendiente) ──────────

export const deudasAPI = {
  listar: () => api.get('/deudas/'),
}

// ── Finanzas ──────────────────────────────────────────────────────────────────

export const finanzasAPI = {
  listarGastos:    ()           => api.get('/finanzas/gastos'),
  crearGasto:      (data)       => api.post('/finanzas/gastos', data),
  actualizarGasto: (id, data)   => api.patch(`/finanzas/gastos/${id}`, data),
  eliminarGasto:   (id)         => api.delete(`/finanzas/gastos/${id}`),
  resumen:         (mes, anio)  => api.get(`/finanzas/resumen?mes=${mes}&anio=${anio}`),
}

// ── Dashboard ─────────────────────────────────────────────────────────────────

export const dashboardAPI = {
  kpis: (mes, anio) => api.get(`/dashboard/?mes=${mes}&anio=${anio}`),
}

// ── Configuración ─────────────────────────────────────────────────────────────

export const configuracionAPI = {
  obtener:    ()     => api.get('/configuracion/'),
  actualizar: (data) => api.patch('/configuracion/', data),
}

// ── Horarios (clases + reservaciones) ────────────────────────────────────────

export const horariosAPI = {
  listarClases:        (params = {}) => api.get('/horarios/clases', { params }),
  crearClase:          (data)        => api.post('/horarios/clases', data),
  actualizarClase:     (id, data)    => api.put(`/horarios/clases/${id}`, data),
  cancelarClase:       (id)          => api.patch(`/horarios/clases/${id}/cancelar`),
  eliminarClase:       (id)          => api.delete(`/horarios/clases/${id}`),
  listarReservaciones: (claseId)     => api.get(`/horarios/clases/${claseId}/reservaciones`),
  reservar:            (claseId, data) => api.post(`/horarios/clases/${claseId}/reservaciones`, data),
  actualizarReservacion: (id, data)  => api.put(`/horarios/reservaciones/${id}`, data),
}

// ── Instructores ──────────────────────────────────────────────────────────────

export const instructoresAPI = {
  listar:     (params = {}) => api.get('/instructores/', { params }),
  crear:      (data)        => api.post('/instructores/', data),
  actualizar: (id, data)    => api.patch(`/instructores/${id}`, data),
  desactivar: (id)          => api.patch(`/instructores/${id}/desactivar`),
  eliminar:   (id)          => api.delete(`/instructores/${id}`),
  reporte:    (mes, anio)   => api.get('/instructores/reporte', { params: { mes, anio } }),
}

// ── Facturas ──────────────────────────────────────────────────────────────────

export const facturasAPI = {
  ventaPdf:      (id) => `${BASE}/facturas/venta/${id}/pdf`,
  ventaHtml:     (id) => `${BASE}/facturas/venta/${id}/html`,
  membresiaPdf:  (id) => `${BASE}/facturas/membresia/${id}/pdf`,
  membresiaHtml: (id) => `${BASE}/facturas/membresia/${id}/html`,
}

export default api
