import api from '@app-services/api'

// Best-effort: si el POST falla (backend caído, sin red), no hace nada más
// — reportar el error no puede en sí mismo generar un error nuevo.
export function reportError(mensaje, stack, contexto) {
  api.post('/errores-frontend', {
    mensaje: String(mensaje ?? 'Error desconocido').slice(0, 2000),
    stack:   stack ? String(stack).slice(0, 5000) : null,
    url:     window.location.href,
    contexto,
  }).catch(() => {})
}

// Se llama una sola vez al arrancar cada app (en main.jsx) — captura lo que
// el ErrorBoundary no puede: errores fuera del árbol de React (handlers de
// eventos, timers) y promesas rechazadas sin catch.
export function iniciarCapturaGlobalDeErrores() {
  window.addEventListener('error', (evento) => {
    reportError(evento.message, evento.error?.stack, 'window-error')
  })

  window.addEventListener('unhandledrejection', (evento) => {
    const razon = evento.reason
    reportError(razon?.message ?? String(razon), razon?.stack, 'unhandled-rejection')
  })
}
