import js from '@eslint/js'
import globals from 'globals'
import react from 'eslint-plugin-react'
import reactHooks from 'eslint-plugin-react-hooks'
import reactRefresh from 'eslint-plugin-react-refresh'

export default [
  { ignores: ['dist'] },
  {
    files: ['**/*.{js,jsx}'],
    languageOptions: {
      ecmaVersion: 2020,
      globals: globals.browser,
      parserOptions: {
        ecmaVersion: 'latest',
        ecmaFeatures: { jsx: true },
        sourceType: 'module',
      },
    },
    plugins: {
      react,
      'react-hooks': reactHooks,
      'react-refresh': reactRefresh,
    },
    settings: {
      react: { version: 'detect' },
    },
    rules: {
      ...js.configs.recommended.rules,
      ...react.configs.recommended.rules,
      ...reactHooks.configs.recommended.rules,
      'react/prop-types': 'off',
      'react/react-in-jsx-scope': 'off',
      'react-refresh/only-export-components': ['warn', { allowConstantExport: true }],
      // catch {} vacío es intencional en reportError.js (best-effort, no
      // puede en sí mismo generar un error nuevo) — sin esto, no-empty lo
      // marca como error aunque el vacío sea la decisión correcta.
      'no-empty': ['error', { allowEmptyCatch: true }],
    },
  },
  {
    // describe/it/expect/vi/etc son globals inyectados por vitest
    // (test.globals: true en vite.config.js) — sin esto, ESLint los marca
    // como no-undef en todos los *.test.js(x).
    files: ['**/*.test.{js,jsx}', 'src/test-setup.js'],
    languageOptions: {
      globals: globals.vitest,
    },
  },
]
