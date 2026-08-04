/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './proximamente.html', './src/**/*.{html,js}'],
  darkMode: 'class',
  theme: {
    extend: {
      colors: {
        // Portado 1:1 desde frontend/src/index.css (paleta real de la app:
        // azul acero + menta + crema). Antes eran valores Material Design
        // generados por Stitch, sin relación con el producto real.
        background: '#f0f2f5',
        surface: '#ffffff',
        'surface-container': '#f0f6f4',
        'surface-container-low': '#f5f6f8',
        primary: '#34526e',
        // Oscurecidos 10% de brillo (mismo tono/saturación, escalado
        // uniforme hacia negro) respecto al valor original portado de la
        // app — #5f82a3 y #648096 daban ~4.0:1 y ~4.14:1 de contraste
        // contra blanco (texto de cuerpo, footer y botones outline), por
        // debajo del mínimo WCAG AA de 4.5:1. Estos valores dan ~4.82:1 y
        // ~4.96:1.
        'primary-container': '#567593',
        'on-primary': '#ffffff',
        'on-primary-container': '#dce8f2',
        secondary: '#1e413c',
        'secondary-container': '#aed6cf',
        'on-secondary-fixed-variant': '#1e413c',
        'on-surface': '#1c2a37',
        'on-surface-variant': '#5a7387',
        'outline-variant': '#c8dae8',
        warning: '#f0c878',
        'warning-text': '#50370a',
      },
      borderRadius: {
        DEFAULT: '0.25rem',
        lg: '0.5rem',
        xl: '0.75rem',
        full: '9999px',
      },
      spacing: {
        'stack-md': '16px',
        'section-v-padding': '120px',
        gutter: '24px',
        'container-max-width': '1280px',
        'stack-sm': '8px',
        'stack-lg': '32px',
      },
      maxWidth: {
        'container-max-width': '1280px',
      },
      fontFamily: {
        // Mismo sistema tipográfico que la app: Google Sans Flex para todo
        // titular/cuerpo, Outfit para números. Boldonse queda reservado al
        // wordmark "DarkCross" (ver index.html), igual que en el sidebar.
        'body-md': ['"Google Sans Flex"', 'sans-serif'],
        'label-sm': ['"Google Sans Flex"', 'sans-serif'],
        'display-lg': ['"Google Sans Flex"', 'sans-serif'],
        'headline-xl': ['"Google Sans Flex"', 'sans-serif'],
        'body-lg': ['"Google Sans Flex"', 'sans-serif'],
        'headline-lg': ['"Google Sans Flex"', 'sans-serif'],
        'metric-xl': ['Outfit', 'sans-serif'],
        wordmark: ['Boldonse', 'sans-serif'],
      },
      fontSize: {
        'body-md': ['16px', { lineHeight: '1.6', letterSpacing: '0em', fontWeight: '400' }],
        'label-sm': ['13px', { lineHeight: '1.0', letterSpacing: '0.05em', fontWeight: '500' }],
        'display-lg': ['72px', { lineHeight: '1.1', letterSpacing: '-0.04em', fontWeight: '800' }],
        'headline-xl': ['48px', { lineHeight: '1.2', letterSpacing: '-0.02em', fontWeight: '700' }],
        'body-lg': ['18px', { lineHeight: '1.6', letterSpacing: '0em', fontWeight: '400' }],
        'headline-lg': ['32px', { lineHeight: '1.2', letterSpacing: '-0.02em', fontWeight: '700' }],
        'display-lg-mobile': ['44px', { lineHeight: '1.1', letterSpacing: '-0.02em', fontWeight: '800' }],
        'metric-xl': ['56px', { lineHeight: '1.0', letterSpacing: '-0.02em', fontWeight: '600' }],
      },
    },
  },
  plugins: [],
}
