import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import PosProductoGrid from './PosProductoGrid.jsx'

function producto(overrides = {}) {
  return { id: 1, nombre: 'Proteína', precio_venta: 25, stock: 10, imagen_url: null, ...overrides }
}

describe('PosProductoGrid', () => {
  it('cargando=true muestra 12 skeletons y ningún producto', () => {
    render(<PosProductoGrid productos={[producto()]} busqueda="" onBusquedaChange={() => {}} cargando={true} carrito={[]} onAgregar={() => {}} />)
    expect(document.querySelectorAll('.pos-card-skeleton')).toHaveLength(12)
    expect(screen.queryByText('Proteína')).not.toBeInTheDocument()
  })

  it('sin productos y sin búsqueda: mensaje de "no hay stock"', () => {
    render(<PosProductoGrid productos={[]} busqueda="" onBusquedaChange={() => {}} cargando={false} carrito={[]} onAgregar={() => {}} />)
    expect(screen.getByText('No hay productos con stock disponible.')).toBeInTheDocument()
  })

  it('sin productos pero CON búsqueda activa: mensaje de "sin resultados", no el de stock', () => {
    render(<PosProductoGrid productos={[]} busqueda="xyz" onBusquedaChange={() => {}} cargando={false} carrito={[]} onAgregar={() => {}} />)
    expect(screen.getByText('Sin resultados.')).toBeInTheDocument()
  })

  it('muestra nombre, precio formateado y stock de cada producto', () => {
    render(<PosProductoGrid productos={[producto({ precio_venta: 12.5, stock: 4 })]} busqueda="" onBusquedaChange={() => {}} cargando={false} carrito={[]} onAgregar={() => {}} />)
    expect(screen.getByText('Proteína')).toBeInTheDocument()
    expect(screen.getByText('$12.50')).toBeInTheDocument()
    expect(screen.getByText('Stock: 4')).toBeInTheDocument()
  })

  it('marca visualmente stock bajo (<=3) con la clase stock-bajo', () => {
    render(<PosProductoGrid productos={[producto({ stock: 2 })]} busqueda="" onBusquedaChange={() => {}} cargando={false} carrito={[]} onAgregar={() => {}} />)
    expect(screen.getByText('Stock: 2')).toHaveClass('stock-bajo')
  })

  it('clickear la card llama a onAgregar con el producto completo', async () => {
    const user = userEvent.setup()
    const onAgregar = vi.fn()
    const p = producto()
    render(<PosProductoGrid productos={[p]} busqueda="" onBusquedaChange={() => {}} cargando={false} carrito={[]} onAgregar={onAgregar} />)
    await user.click(screen.getByText('Proteína').closest('button'))
    expect(onAgregar).toHaveBeenCalledWith(p)
  })

  it('un producto ya en el carrito muestra su cantidad como badge', () => {
    const p = producto({ id: 5 })
    render(
      <PosProductoGrid
        productos={[p]}
        busqueda=""
        onBusquedaChange={() => {}}
        cargando={false}
        carrito={[{ producto: p, cantidad: 3 }]}
        onAgregar={() => {}}
      />
    )
    expect(screen.getByText('3')).toBeInTheDocument()
    expect(screen.getByText('Proteína').closest('button')).toHaveClass('en-carrito')
  })

  it('escribir en el buscador llama a onBusquedaChange', async () => {
    const user = userEvent.setup()
    const onBusquedaChange = vi.fn()
    render(<PosProductoGrid productos={[]} busqueda="" onBusquedaChange={onBusquedaChange} cargando={false} carrito={[]} onAgregar={() => {}} />)
    await user.type(screen.getByPlaceholderText('Buscar producto...'), 'a')
    expect(onBusquedaChange).toHaveBeenCalledWith('a')
  })
})
