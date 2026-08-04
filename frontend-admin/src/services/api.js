import axios from 'axios'

const BASE = import.meta.env.VITE_API_URL ?? '/api'
const STORAGE_KEY = 'darkcross_admin_key'

// Sin JWT ni cookies acá — el "login" es una clave estática de servidor
// (X-Platform-Key, la misma que usa el backend en platform_admin.py) que
// vive en localStorage y viaja en cada request.

export function getClave() {
  return localStorage.getItem(STORAGE_KEY) || ''
}

export function setClave(clave) {
  localStorage.setItem(STORAGE_KEY, clave)
}

export function borrarClave() {
  localStorage.removeItem(STORAGE_KEY)
}

const api = axios.create({ baseURL: BASE })

api.interceptors.request.use(config => {
  config.headers['X-Platform-Key'] = getClave()
  return config
})

// 403 = clave inválida o revocada — nunca es "todavía no puso la clave"
// (eso es un 422 de FastAPI por header faltante, no lo tratamos como sesión
// expirada). Se lo avisamos a App.jsx para que vuelva a mostrar el login.
let onSesionInvalida = null
export function setSesionInvalidaHandler(fn) {
  onSesionInvalida = fn
}

api.interceptors.response.use(
  res => res,
  err => {
    if (err.response?.status === 403) {
      borrarClave()
      onSesionInvalida?.()
    }
    return Promise.reject(err)
  }
)

export const analyticsAPI = {
  ping:    ()  => api.get('/admin/analytics/ping'),
  resumen: ()  => api.get('/admin/analytics/resumen'),
  gyms:    ()  => api.get('/admin/analytics/gyms'),
}

export const suscripcionesAdminAPI = {
  pagosPendientes:   ()          => api.get('/admin/suscripciones/pagos-pendientes'),
  confirmarPago:     (gymId, datos) => api.post(`/admin/suscripciones/${gymId}/confirmar`, datos),
  rechazarPago:      (gymId, datos) => api.post(`/admin/suscripciones/${gymId}/rechazar`, datos),
  cambiarTier:       (gymId, tier)  => api.post(`/admin/suscripciones/${gymId}/cambiar-tier`, { tier }),
  suspender:         (gymId, notas) => api.post(`/admin/suscripciones/${gymId}/suspender`, { notas: notas || null }),
  reactivar:         (gymId)        => api.post(`/admin/suscripciones/${gymId}/reactivar`),
}

export default api
