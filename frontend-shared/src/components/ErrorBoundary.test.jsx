import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'

const postMock = vi.fn(() => Promise.resolve())
vi.mock('@app-services/api', () => ({
  default: { post: postMock },
  miembrosAPI: {},
}))

const { ErrorBoundary } = await import('./ErrorBoundary.jsx')

function Bomba() {
  throw new Error('boom de prueba')
}

describe('ErrorBoundary', () => {
  beforeEach(() => {
    postMock.mockClear()
    vi.spyOn(console, 'error').mockImplementation(() => {}) // React loguea el throw, no ensucia el output del test
  })

  it('renderiza a los hijos normalmente cuando no hay error', () => {
    render(<ErrorBoundary><p>Todo bien</p></ErrorBoundary>)
    expect(screen.getByText('Todo bien')).toBeInTheDocument()
  })

  it('cuando un hijo tira, muestra el fallback en vez de crashear toda la página', () => {
    render(<ErrorBoundary><Bomba /></ErrorBoundary>)
    expect(screen.getByText('Algo salió mal')).toBeInTheDocument()
    expect(screen.getByText('Recargar')).toBeInTheDocument()
  })

  it('reporta el error al backend vía @app-services/api', () => {
    render(<ErrorBoundary><Bomba /></ErrorBoundary>)
    expect(postMock).toHaveBeenCalledTimes(1)
    const [url, body] = postMock.mock.calls[0]
    expect(url).toBe('/errores-frontend')
    expect(body.mensaje).toBe('boom de prueba')
    expect(body.contexto).toBe('react-error-boundary')
  })

  it('el botón Recargar dispara window.location.reload', () => {
    const reloadMock = vi.fn()
    const originalLocation = window.location
    delete window.location
    window.location = { ...originalLocation, reload: reloadMock }

    render(<ErrorBoundary><Bomba /></ErrorBoundary>)
    fireEvent.click(screen.getByText('Recargar'))
    expect(reloadMock).toHaveBeenCalledTimes(1)

    window.location = originalLocation
  })
})
