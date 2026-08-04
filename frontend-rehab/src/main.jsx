import React from 'react'
import ReactDOM from 'react-dom/client'
import App from './App.jsx'
import { ErrorBoundary } from '@shared/components/ErrorBoundary'
import { iniciarCapturaGlobalDeErrores } from '@shared/utils/reportError'
import '@shared/index.css'

iniciarCapturaGlobalDeErrores()

ReactDOM.createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <ErrorBoundary>
      <App />
    </ErrorBoundary>
  </React.StrictMode>
)
