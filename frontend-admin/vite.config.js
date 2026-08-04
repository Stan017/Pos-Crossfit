import { fileURLToPath } from 'node:url'
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// Solo para el ErrorBoundary/reportError compartido (ver frontend-shared/) —
// frontend-admin no comparte páginas de negocio con frontend/frontend-rehab,
// es un panel distinto, pero no tiene sentido triplicar ese código.
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
    port: 5176,
    fs: {
      allow: ['.', sharedSrc],
    },
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/api/, ''),
      },
      // Comprobantes de transferencia — ruta protegida por auth en el
      // backend, sin el prefijo /api.
      '/archivos': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
    },
  },

  build: {
    rollupOptions: {
      output: {
        manualChunks: {
          'vendor-react': ['react', 'react-dom', 'react-router-dom'],
          'vendor-axios': ['axios'],
        },
      },
    },
    chunkSizeWarningLimit: 400,
  },
})
