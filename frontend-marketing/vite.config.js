import { defineConfig } from 'vite'
import { resolve } from 'path'

export default defineConfig({
  server: {
    // Puerto fijo: frontend/ usa 5173, frontend-rehab/ usa 5174 — con los
    // tres corriendo a la vez (start.bat), cada uno necesita el suyo fijo.
    port: 5175,
  },
  build: {
    chunkSizeWarningLimit: 400,
    rollupOptions: {
      // Multi-página: proximamente.html es la página compartida para los
      // links del footer que todavía no tienen contenido real (ver #6 del
      // audit de landing) — sin esto, Vite solo empaqueta index.html.
      input: {
        main: resolve(__dirname, 'index.html'),
        proximamente: resolve(__dirname, 'proximamente.html'),
        privacyPolicy: resolve(__dirname, 'privacy-policy.html'),
        termsOfService: resolve(__dirname, 'terms-of-service.html'),
        cookiePolicy: resolve(__dirname, 'cookie-policy.html'),
      },
    },
  },
})
