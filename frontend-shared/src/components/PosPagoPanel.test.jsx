import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import PosPagoPanel from './PosPagoPanel.jsx'

function propsBase(overrides = {}) {
  return {
    subtotal: 100, montoIva: 0, totalVenta: 100, porcentajeIva: 0,
    onPorcentajeIvaChange: () => {}, ivaDefault: 15,
    metodoPago: 'efectivo', onMetodoPagoChange: () => {},
    montoRecibido: '', onMontoRecibidoChange: () => {}, cambio: null,
    esAbono: false, onEsAbonoChange: () => {},
    montoAbono: '', onMontoAbonoChange: () => {},
    errorPago: '',
    cobrando: false, onCobrar: () => {}, onLimpiar: () => {},
    ...overrides,
  }
}

describe('PosPagoPanel', () => {
  it('sin IVA muestra solo el total, sin desglose de subtotal', () => {
    render(<PosPagoPanel {...propsBase()} />)
    expect(screen.queryByText('Subtotal')).not.toBeInTheDocument()
    expect(screen.getByText('$100.00')).toBeInTheDocument()
  })

  it('activar el checkbox de IVA usa ivaDefault, no un valor fijo', async () => {
    const user = userEvent.setup()
    const onPorcentajeIvaChange = vi.fn()
    render(<PosPagoPanel {...propsBase({ ivaDefault: 12 })} onPorcentajeIvaChange={onPorcentajeIvaChange} />)
    await user.click(screen.getByRole('checkbox'))
    expect(onPorcentajeIvaChange).toHaveBeenCalledWith(12)
  })

  it('con IVA>0 muestra el desglose subtotal/IVA/total', () => {
    render(<PosPagoPanel {...propsBase({ porcentajeIva: 15, montoIva: 15, totalVenta: 115 })} />)
    expect(screen.getByText('Subtotal')).toBeInTheDocument()
    expect(screen.getByText('IVA (15%)')).toBeInTheDocument()
    expect(screen.getByText('$115.00')).toBeInTheDocument()
  })

  it('clic en Transferencia llama a onMetodoPagoChange y marca el botón activo', async () => {
    const user = userEvent.setup()
    const onMetodoPagoChange = vi.fn()
    render(<PosPagoPanel {...propsBase()} onMetodoPagoChange={onMetodoPagoChange} />)
    await user.click(screen.getByText('📲 Transferencia'))
    expect(onMetodoPagoChange).toHaveBeenCalledWith('transferencia')
  })

  it('metodoPago=transferencia oculta el campo "Monto recibido" (solo aplica a efectivo)', () => {
    render(<PosPagoPanel {...propsBase({ metodoPago: 'transferencia' })} />)
    expect(screen.queryByText('Monto recibido')).not.toBeInTheDocument()
  })

  it('efectivo + pago completo muestra "Monto recibido" y el cambio si corresponde', () => {
    render(<PosPagoPanel {...propsBase({ metodoPago: 'efectivo', esAbono: false, montoRecibido: '150', cambio: 50 })} />)
    expect(screen.getByText('Monto recibido')).toBeInTheDocument()
    expect(screen.getByText('Cambio')).toBeInTheDocument()
    expect(screen.getByText('$50.00')).toBeInTheDocument()
  })

  it('esAbono=true reemplaza "Monto recibido" por "Monto del abono" y muestra saldo pendiente', () => {
    render(<PosPagoPanel {...propsBase({ esAbono: true, montoAbono: '40', totalVenta: 100 })} />)
    expect(screen.queryByText('Monto recibido')).not.toBeInTheDocument()
    expect(screen.getByText('Monto del abono')).toBeInTheDocument()
    expect(screen.getByText('Saldo pendiente')).toBeInTheDocument()
    expect(screen.getByText('$60.00')).toBeInTheDocument()
  })

  it('errorPago muestra el mensaje y deshabilita el botón de cobrar', () => {
    render(<PosPagoPanel {...propsBase({ errorPago: 'Monto insuficiente' })} />)
    expect(screen.getByText('Monto insuficiente')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /Cobrar/ })).toBeDisabled()
  })

  it('cobrando=true deshabilita el botón y cambia su texto', () => {
    render(<PosPagoPanel {...propsBase({ cobrando: true })} />)
    expect(screen.getByRole('button', { name: 'Procesando...' })).toBeDisabled()
  })

  it('clic en Cobrar llama a onCobrar cuando no hay error', async () => {
    const user = userEvent.setup()
    const onCobrar = vi.fn()
    render(<PosPagoPanel {...propsBase()} onCobrar={onCobrar} />)
    await user.click(screen.getByRole('button', { name: /Cobrar \$100.00/ }))
    expect(onCobrar).toHaveBeenCalledTimes(1)
  })
})
