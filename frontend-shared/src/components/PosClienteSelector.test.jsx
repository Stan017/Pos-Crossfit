import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'

const listarMock = vi.fn()
const crearMock  = vi.fn()
vi.mock('@app-services/api', () => ({
  default: { post: vi.fn(), get: vi.fn(), put: vi.fn(), patch: vi.fn(), delete: vi.fn() },
  miembrosAPI: { listar: (...args) => listarMock(...args), crear: (...args) => crearMock(...args) },
}))

const { default: PosClienteSelector } = await import('./PosClienteSelector.jsx')

describe('PosClienteSelector', () => {
  beforeEach(() => {
    listarMock.mockReset().mockResolvedValue({ data: [] })
    crearMock.mockReset()
  })

  it('con un cliente ya seleccionado, muestra su nombre y no el buscador', () => {
    render(
      <PosClienteSelector
        cliente={{ id: 1, nombre: 'Ana', apellido: 'Lopez' }}
        onSeleccionarCliente={() => {}}
        onQuitarCliente={() => {}}
      />
    )
    expect(screen.getByText(/Ana Lopez/)).toBeInTheDocument()
    expect(screen.queryByPlaceholderText('Buscar cliente...')).not.toBeInTheDocument()
  })

  it('el botón ✕ del cliente seleccionado llama a onQuitarCliente', async () => {
    const user = userEvent.setup()
    const onQuitarCliente = vi.fn()
    render(
      <PosClienteSelector
        cliente={{ id: 1, nombre: 'Ana', apellido: 'Lopez' }}
        onSeleccionarCliente={() => {}}
        onQuitarCliente={onQuitarCliente}
      />
    )
    await user.click(screen.getByText('✕'))
    expect(onQuitarCliente).toHaveBeenCalledTimes(1)
  })

  it('escribir en el buscador dispara miembrosAPI.listar (debounced) y muestra sugeridos', async () => {
    listarMock.mockResolvedValue({ data: [{ id: 2, nombre: 'Berta', apellido: 'Ruiz', telefono: '099' }] })
    const user = userEvent.setup()
    render(<PosClienteSelector cliente={null} onSeleccionarCliente={() => {}} onQuitarCliente={() => {}} />)

    await user.type(screen.getByPlaceholderText('Buscar cliente...'), 'ber')

    await waitFor(() => expect(listarMock).toHaveBeenCalledWith({ q: 'ber' }), { timeout: 1000 })
    await waitFor(() => expect(screen.getByText(/Berta Ruiz/)).toBeInTheDocument())
  })

  it('elegir un sugerido llama a onSeleccionarCliente y limpia la búsqueda', async () => {
    listarMock.mockResolvedValue({ data: [{ id: 3, nombre: 'Carlos', apellido: 'Diaz' }] })
    const user = userEvent.setup()
    const onSeleccionarCliente = vi.fn()
    render(<PosClienteSelector cliente={null} onSeleccionarCliente={onSeleccionarCliente} onQuitarCliente={() => {}} />)

    await user.type(screen.getByPlaceholderText('Buscar cliente...'), 'car')
    await waitFor(() => expect(screen.getByText(/Carlos Diaz/)).toBeInTheDocument(), { timeout: 1000 })
    await user.click(screen.getByText(/Carlos Diaz/))

    expect(onSeleccionarCliente).toHaveBeenCalledWith({ id: 3, nombre: 'Carlos', apellido: 'Diaz' })
    expect(screen.getByPlaceholderText('Buscar cliente...')).toHaveValue('')
  })

  it('el botón de "nuevo cliente" abre el formulario de alta rápida', async () => {
    const user = userEvent.setup()
    render(<PosClienteSelector cliente={null} onSeleccionarCliente={() => {}} onQuitarCliente={() => {}} />)
    await user.click(screen.getByTitle('Registrar nuevo cliente'))
    expect(screen.getByText('Nuevo cliente')).toBeInTheDocument()
  })

  it('registrar cliente rápido llama a miembrosAPI.crear y selecciona el resultado', async () => {
    crearMock.mockResolvedValue({ data: { id: 9, nombre: 'Diego', apellido: '—' } })
    const user = userEvent.setup()
    const onSeleccionarCliente = vi.fn()
    render(<PosClienteSelector cliente={null} onSeleccionarCliente={onSeleccionarCliente} onQuitarCliente={() => {}} />)

    await user.click(screen.getByTitle('Registrar nuevo cliente'))
    await user.type(screen.getByPlaceholderText('Nombre *'), 'Diego')
    await user.click(screen.getByText('Guardar'))

    await waitFor(() => expect(crearMock).toHaveBeenCalledWith({
      nombre: 'Diego', apellido: '—', telefono: null,
    }))
    await waitFor(() => expect(onSeleccionarCliente).toHaveBeenCalledWith({ id: 9, nombre: 'Diego', apellido: '—' }))
  })

  it('si crear cliente falla, avisa con alert y no revienta', async () => {
    crearMock.mockRejectedValue(new Error('500'))
    const alertMock = vi.spyOn(window, 'alert').mockImplementation(() => {})
    const user = userEvent.setup()
    render(<PosClienteSelector cliente={null} onSeleccionarCliente={() => {}} onQuitarCliente={() => {}} />)

    await user.click(screen.getByTitle('Registrar nuevo cliente'))
    await user.type(screen.getByPlaceholderText('Nombre *'), 'Fallido')
    await user.click(screen.getByText('Guardar'))

    await waitFor(() => expect(alertMock).toHaveBeenCalledWith('No se pudo registrar el cliente.'))
    alertMock.mockRestore()
  })
})
