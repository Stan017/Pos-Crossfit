// Stub para el alias @app-services/api dentro de frontend-shared: acá no hay
// una sola app real detrás del alias (@app-services es POR APP, ver
// vite.config.js de frontend/frontend-rehab), así que los tests que ejercitan
// componentes con esta dependencia la reemplazan con vi.mock('@app-services/api', ...).
// Este archivo solo necesita existir para que ese specifier resuelva a algo.
export const miembrosAPI = {
  listar:     () => Promise.resolve({ data: [] }),
  obtener:    () => Promise.resolve({ data: null }),
  crear:      () => Promise.resolve({ data: null }),
  actualizar: () => Promise.resolve({ data: null }),
  reactivar:  () => Promise.resolve({ data: null }),
  desactivar: () => Promise.resolve({}),
}

export default {
  get:    () => Promise.resolve({ data: null }),
  post:   () => Promise.resolve({ data: null }),
  put:    () => Promise.resolve({ data: null }),
  patch:  () => Promise.resolve({ data: null }),
  delete: () => Promise.resolve({ data: null }),
}
