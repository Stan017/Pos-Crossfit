import { fileURLToPath } from 'node:url'
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// Páginas/hooks/utils/CSS que son 100% idénticos entre frontend/ y
// frontend-rehab/ viven en frontend-shared/ — se importan vía @shared/...
// en vez de copiarse en cada app. Ver frontend-shared/README o el diff que
// dejó el corte: 22 archivos, ninguno con vocabulario de vertical.
const sharedSrc = fileURLToPath(new URL('../frontend-shared/src', import.meta.url))

export default defineConfig({
  plugins: [react()],

  resolve: {
    alias: {
      '@shared': sharedSrc,
      '@app-services': fileURLToPath(new URL('./src/services', import.meta.url)),
    },
  },

  server: {
    port: 5173,
    fs: {
      // Vite por defecto no sirve archivos fuera de la raíz del proyecto —
      // frontend-shared/ vive al lado, no adentro, de frontend/.
      allow: ['.', sharedSrc],
    },
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/api/, ''),
      },
      // Archivos subidos (comprobantes, fotos de producto) — ruta protegida
      // por auth en el backend, sin el prefijo /api.
      '/archivos': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
    },
  },

  build: {
    // Separar chunks por vendor para mejor cache en el browser
    rollupOptions: {
      output: {
        manualChunks: {
          // React core — cambia muy poco, se cachea siempre
          'vendor-react': ['react', 'react-dom', 'react-router-dom'],
          // Axios — librería estable, chunk separado
          'vendor-axios': ['axios'],
        },
      },
    },
    // Avisar si algún chunk supera 400 KB (por defecto 500)
    chunkSizeWarningLimit: 400,
  },
})
