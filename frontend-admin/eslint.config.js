import js from '@eslint/js'
import globals from 'globals'
import react from 'eslint-plugin-react'
import reactHooks from 'eslint-plugin-react-hooks'
import reactRefresh from 'eslint-plugin-react-refresh'

// Config estándar del template de Vite+React + eslint-plugin-react: sin este
// último, no-unused-vars no sabe que <Dashboard /> en JSX cuenta como uso de
// la variable `Dashboard` (JSXIdentifier no es un Identifier normal para
// eslint-scope) — cualquier componente importado y solo usado como etiqueta
// se marcaría "sin usar" en falso. react-hooks atrapa dependencias mal
// puestas en useEffect/useCallback (bugs reales y sutiles); react-refresh
// exige que cada archivo exporte componentes de forma consistente con Fast
// Refresh.
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
      'react/prop-types': 'off',           // proyecto sin PropTypes/TS — no aplica
      'react/react-in-jsx-scope': 'off',    // JSX transform automático (React 18 + Vite), no hace falta importar React
      'react-refresh/only-export-components': ['warn', { allowConstantExport: true }],
      // catch {} vacío es intencional en varios lugares (logout best-effort,
      // refresh silencioso que no debe bloquear la acción principal) — mismo
      // patrón que .catch(() => {}) en reportError.js. Sin esto, no-empty los
      // marca como error aunque el vacío sea la decisión correcta.
      'no-empty': ['error', { allowEmptyCatch: true }],
    },
  },
]
