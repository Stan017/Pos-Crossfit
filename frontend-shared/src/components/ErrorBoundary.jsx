import { Component } from 'react'
import { reportError } from '../utils/reportError'

const estiloFondo = {
  display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center',
  minHeight: '100vh', padding: '2rem', textAlign: 'center', fontFamily: 'sans-serif', gap: '0.75rem',
}

const estiloBoton = {
  marginTop: '0.5rem', padding: '0.6rem 1.4rem', fontSize: '1rem',
  border: 'none', borderRadius: '6px', cursor: 'pointer',
  background: '#1f2937', color: '#fff',
}

// Sin CSS externo a propósito: cada vertical tiene su propio sistema de
// diseño (Clientes.css, index.css) y este fallback tiene que verse bien sin
// depender de que esas clases existan — es lo único que se muestra cuando
// React mismo se rompió.
export class ErrorBoundary extends Component {
  constructor(props) {
    super(props)
    this.state = { crasheado: false }
  }

  static getDerivedStateFromError() {
    return { crasheado: true }
  }

  componentDidCatch(error, info) {
    reportError(error?.message, error?.stack ?? info?.componentStack, 'react-error-boundary')
  }

  render() {
    if (this.state.crasheado) {
      return (
        <div style={estiloFondo}>
          <h1>Algo salió mal</h1>
          <p>La aplicación encontró un error inesperado. Ya quedó reportado.</p>
          <button style={estiloBoton} onClick={() => window.location.reload()}>
            Recargar
          </button>
        </div>
      )
    }
    return this.props.children
  }
}
