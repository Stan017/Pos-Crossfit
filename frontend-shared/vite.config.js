import { fileURLToPath } from 'url'
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// Config exclusiva para correr los tests de frontend-shared en aislamiento.
// Las apps reales (frontend/, frontend-rehab/) NO usan este archivo — ellas
// resuelven @shared/@app-services con sus propios vite.config.js, apuntando
// a src/services propio de cada una. Acá @app-services apunta a un stub
// (ver src/test-stubs/api.js) porque no hay una sola app "dueña" de este
// paquete compartido.
export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      '@app-services': fileURLToPath(new URL('./src/test-stubs', import.meta.url)),
    },
  },
  test: {
    environment: 'jsdom',
    setupFiles: ['./src/test-setup.js'],
    // true: @testing-library/react detecta el afterEach global y limpia el
    // DOM entre tests solo. En false, los renders se acumulan dentro del
    // mismo archivo y "getByText" empieza a fallar por elementos duplicados.
    globals: true,
  },
})
