import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import PosCarritoItems from './PosCarritoItems.jsx'

function producto(overrides = {}) {
  return { id: 1, nombre: 'Proteína', precio_venta: 25, ...overrides }
}

describe('PosCarritoItems', () => {
  it('carrito vacío muestra el mensaje de instrucción, no una lista vacía', () => {
    render(<PosCarritoItems carrito={[]} onCambiarCantidad={() => {}} onQuitar={() => {}} />)
    expect(screen.getByText('Selecciona productos del panel izquierdo')).toBeInTheDocument()
  })

  it('muestra nombre, cantidad y subtotal calculado por ítem', () => {
    render(
      <PosCarritoItems
        carrito={[{ producto: producto(), cantidad: 3 }]}
        onCambiarCantidad={() => {}}
        onQuitar={() => {}}
      />
    )
    expect(screen.getByText('Proteína')).toBeInTheDocument()
    expect(screen.getByText('3')).toBeInTheDocument()
    expect(screen.getByText('$75.00')).toBeInTheDocument() // 25 * 3
  })

  it('los botones +/- llaman a onCambiarCantidad con el delta correcto', async () => {
    const user = userEvent.setup()
    const onCambiarCantidad = vi.fn()
    render(
      <PosCarritoItems
        carrito={[{ producto: producto({ id: 7 }), cantidad: 2 }]}
        onCambiarCantidad={onCambiarCantidad}
        onQuitar={() => {}}
      />
    )
    await user.click(screen.getByText('+'))
    expect(onCambiarCantidad).toHaveBeenCalledWith(7, 1)
    await user.click(screen.getByText('−'))
    expect(onCambiarCantidad).toHaveBeenCalledWith(7, -1)
  })

  it('el botón quitar llama a onQuitar con el id del producto', async () => {
    const user = userEvent.setup()
    const onQuitar = vi.fn()
    render(
      <PosCarritoItems
        carrito={[{ producto: producto({ id: 9 }), cantidad: 1 }]}
        onCambiarCantidad={() => {}}
        onQuitar={onQuitar}
      />
    )
    await user.click(screen.getByText('✕'))
    expect(onQuitar).toHaveBeenCalledWith(9)
  })

  it('renderiza una fila por cada producto distinto del carrito', () => {
    render(
      <PosCarritoItems
        carrito={[
          { producto: producto({ id: 1, nombre: 'A' }), cantidad: 1 },
          { producto: producto({ id: 2, nombre: 'B' }), cantidad: 1 },
        ]}
        onCambiarCantidad={() => {}}
        onQuitar={() => {}}
      />
    )
    expect(screen.getByText('A')).toBeInTheDocument()
    expect(screen.getByText('B')).toBeInTheDocument()
  })
})
