import { describe, it, expect } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { useFocusTrap } from './useFocusTrap.js'

function ModalDePrueba({ abierto }) {
  const ref = useFocusTrap(abierto)
  if (!abierto) return null
  return (
    <div ref={ref} data-testid="modal">
      <button>Primero</button>
      <input placeholder="campo" />
      <button>Ultimo</button>
    </div>
  )
}

describe('useFocusTrap', () => {
  it('al abrirse, mueve el foco al primer elemento enfocable del contenedor', () => {
    render(<ModalDePrueba abierto={true} />)
    expect(document.activeElement).toBe(screen.getByText('Primero'))
  })

  it('Tab en el último elemento vuelve al primero (ciclo hacia adelante)', () => {
    render(<ModalDePrueba abierto={true} />)
    screen.getByText('Ultimo').focus()
    fireEvent.keyDown(screen.getByTestId('modal'), { key: 'Tab' })
    expect(document.activeElement).toBe(screen.getByText('Primero'))
  })

  it('Shift+Tab en el primer elemento va al último (ciclo hacia atrás)', () => {
    render(<ModalDePrueba abierto={true} />)
    screen.getByText('Primero').focus()
    fireEvent.keyDown(screen.getByTestId('modal'), { key: 'Tab', shiftKey: true })
    expect(document.activeElement).toBe(screen.getByText('Ultimo'))
  })

  it('devuelve el foco a lo que estaba enfocado antes de abrirse, al cerrar', () => {
    const { rerender } = render(<ModalDePrueba abierto={false} />)
    // Simular manualmente: enfocar algo "afuera" antes de abrir.
    const externo = document.createElement('button')
    externo.textContent = 'externo'
    document.body.appendChild(externo)
    externo.focus()
    expect(document.activeElement).toBe(externo)

    rerender(<ModalDePrueba abierto={true} />)
    expect(document.activeElement).toBe(screen.getByText('Primero'))

    rerender(<ModalDePrueba abierto={false} />)
    expect(document.activeElement).toBe(externo)
    externo.remove()
  })
})
