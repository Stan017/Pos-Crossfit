import { useState, useEffect, useCallback, useMemo } from 'react'
import { productosAPI, ventasAPI, configuracionAPI } from '@app-services/api'
import PosClienteSelector from '../components/PosClienteSelector'
import PosProductoGrid from '../components/PosProductoGrid'
import PosCarritoItems from '../components/PosCarritoItems'
import PosPagoPanel from '../components/PosPagoPanel'
import './POS.css'

export default function POS() {
  // ─── Productos ──────────────────────────────────────────────────────────────
  const [productos, setProductos]   = useState([])
  const [busqueda, setBusqueda]     = useState('')
  const [cargandoProd, setCargandoProd] = useState(true)

  // ─── Carrito ─────────────────────────────────────────────────────────────────
  const [carrito, setCarrito] = useState([])  // [{ producto, cantidad }]

  // ─── Cliente ─────────────────────────────────────────────────────────────────
  const [cliente, setCliente] = useState(null)
  // Fuerza un remount de PosClienteSelector al limpiar el carrito, para que
  // también se resetee su estado interno de búsqueda/alta rápida.
  const [clienteResetKey, setClienteResetKey] = useState(0)

  // ─── Pago ────────────────────────────────────────────────────────────────────
  const [metodoPago, setMetodoPago]     = useState('efectivo')
  const [montoRecibido, setMontoRecibido] = useState('')
  const [esAbono, setEsAbono]           = useState(false)
  const [montoAbono, setMontoAbono]     = useState('')

  // ─── IVA ─────────────────────────────────────────────────────────────────────
  const [ivaDefault, setIvaDefault]   = useState(0)
  const [porcentajeIva, setPorcentajeIva] = useState(0)   // IVA activo en esta venta

  // ─── Estado ──────────────────────────────────────────────────────────────────
  const [cobrando, setCobrando]       = useState(false)
  const [ventaExitosa, setVentaExitosa] = useState(null)

  // ─── Carga de productos ──────────────────────────────────────────────────────

  const cargarProductos = useCallback(async (q = '') => {
    try {
      setCargandoProd(true)
      const res = await productosAPI.listar(q)
      setProductos(res.data.filter(p => p.stock > 0))
    } catch {
      // silencioso — el inventario vacío ya lo indica
    } finally {
      setCargandoProd(false)
    }
  }, [])

  useEffect(() => {
    cargarProductos()
    configuracionAPI.obtener()
      .then(r => { setIvaDefault(r.data.iva_default || 0); setPorcentajeIva(r.data.iva_default || 0) })
      .catch(() => {})
  }, [])

  useEffect(() => {
    const t = setTimeout(() => cargarProductos(busqueda), 300)
    return () => clearTimeout(t)
  }, [busqueda, cargarProductos])

  // ─── Carrito ─────────────────────────────────────────────────────────────────

  function agregar(producto) {
    setCarrito(prev => {
      const existe = prev.find(i => i.producto.id === producto.id)
      if (existe) {
        // No superar el stock disponible
        if (existe.cantidad >= producto.stock) return prev
        return prev.map(i => i.producto.id === producto.id
          ? { ...i, cantidad: i.cantidad + 1 }
          : i
        )
      }
      return [...prev, { producto, cantidad: 1 }]
    })
  }

  function cambiarCantidad(id, delta) {
    setCarrito(prev =>
      prev
        .map(i => {
          if (i.producto.id !== id) return i
          const nueva = i.cantidad + delta
          if (nueva > i.producto.stock) return i   // no superar stock
          return { ...i, cantidad: nueva }
        })
        .filter(i => i.cantidad > 0)
    )
  }

  function quitar(id) {
    setCarrito(prev => prev.filter(i => i.producto.id !== id))
  }

  function limpiarCarrito() {
    setCarrito([])
    setCliente(null)
    setClienteResetKey(k => k + 1)
    setMetodoPago('efectivo')
    setMontoRecibido('')
    setEsAbono(false)
    setMontoAbono('')
    setPorcentajeIva(ivaDefault)
  }

  // ─── Totales ─────────────────────────────────────────────────────────────────

  const subtotal   = useMemo(() => carrito.reduce((s, i) => s + i.producto.precio_venta * i.cantidad, 0), [carrito])
  const montoIva   = useMemo(() => Math.round(subtotal * porcentajeIva / 100 * 100) / 100, [subtotal, porcentajeIva])
  const totalVenta = useMemo(() => Math.round((subtotal + montoIva) * 100) / 100, [subtotal, montoIva])
  const cambio     = useMemo(() => metodoPago === 'efectivo' && montoRecibido
    ? parseFloat(montoRecibido) - totalVenta
    : null, [metodoPago, montoRecibido, totalVenta])

  // Validación derivada del pago actual — el botón "Cobrar" se deshabilita y
  // muestra este mensaje en vez de dejar clicar y recién enterarse por un
  // alert() después del click.
  const errorPago = useMemo(() => {
    if (esAbono) {
      if (montoAbono === '' || montoAbono === null || parseFloat(montoAbono) < 0)
        return 'Ingresa el monto del abono (puede ser 0 si es fiado completo).'
      if (parseFloat(montoAbono) > totalVenta)
        return 'El abono no puede superar el total.'
    }
    if (metodoPago === 'efectivo' && !esAbono && montoRecibido) {
      if (parseFloat(montoRecibido) < totalVenta)
        return 'El monto recibido es menor al total.'
    }
    return null
  }, [esAbono, montoAbono, totalVenta, metodoPago, montoRecibido])

  // ─── Cobrar ──────────────────────────────────────────────────────────────────

  async function cobrar() {
    if (carrito.length === 0 || errorPago) return

    try {
      setCobrando(true)
      const res = await ventasAPI.crear({
        miembro_id:     cliente?.id ?? null,
        porcentaje_iva: porcentajeIva,
        pago_inicial:   esAbono ? parseFloat(montoAbono) : totalVenta,
        metodo_pago:    metodoPago,
        items: carrito.map(i => ({
          producto_id: i.producto.id,
          cantidad:    i.cantidad,
        })),
      })
      setVentaExitosa({
        id:      res.data.id,
        total:   totalVenta,
        cambio:  cambio,
        cliente: cliente,
        esAbono,
        montoAbono: esAbono ? parseFloat(montoAbono) : null,
        saldo:  esAbono ? totalVenta - parseFloat(montoAbono) : 0,
      })
      cargarProductos(busqueda)
    } catch (err) {
      alert(err.response?.data?.detail ?? 'Error al procesar la venta.')
    } finally {
      setCobrando(false)
    }
  }

  function nuevaVenta() {
    limpiarCarrito()
    setVentaExitosa(null)
  }

  // ─── Render ──────────────────────────────────────────────────────────────────

  if (ventaExitosa) {
    return (
      <div className="pos-exito">
        <div className="exito-card">
          <div className="exito-icono">✓</div>
          <h2>Venta registrada</h2>
          {ventaExitosa.cliente && (
            <p className="exito-cliente">{ventaExitosa.cliente.nombre} {ventaExitosa.cliente.apellido ?? ''}</p>
          )}
          <div className="exito-detalle">
            <div className="exito-fila">
              <span>Total</span>
              <span className="num">${ventaExitosa.total.toFixed(2)}</span>
            </div>
            {ventaExitosa.esAbono && (
              <>
                <div className="exito-fila">
                  <span>Abono recibido</span>
                  <span className="num">${ventaExitosa.montoAbono.toFixed(2)}</span>
                </div>
                <div className="exito-fila exito-saldo">
                  <span>Saldo pendiente</span>
                  <span className="num">${ventaExitosa.saldo.toFixed(2)}</span>
                </div>
              </>
            )}
            {ventaExitosa.cambio !== null && ventaExitosa.cambio >= 0 && !ventaExitosa.esAbono && (
              <div className="exito-fila">
                <span>Cambio</span>
                <span className="num">${ventaExitosa.cambio.toFixed(2)}</span>
              </div>
            )}
          </div>
          <button className="btn btn-primary exito-btn" onClick={nuevaVenta}>
            Nueva venta
          </button>
        </div>
      </div>
    )
  }

  return (
    <div className="pos">

      <PosProductoGrid
        productos={productos}
        busqueda={busqueda}
        onBusquedaChange={setBusqueda}
        cargando={cargandoProd}
        carrito={carrito}
        onAgregar={agregar}
      />

      <div className="pos-carrito">
        <PosClienteSelector
          key={clienteResetKey}
          cliente={cliente}
          onSeleccionarCliente={setCliente}
          onQuitarCliente={() => setCliente(null)}
        />

        <PosCarritoItems
          carrito={carrito}
          onCambiarCantidad={cambiarCantidad}
          onQuitar={quitar}
        />

        {carrito.length > 0 && (
          <PosPagoPanel
            subtotal={subtotal}
            montoIva={montoIva}
            totalVenta={totalVenta}
            porcentajeIva={porcentajeIva}
            onPorcentajeIvaChange={setPorcentajeIva}
            ivaDefault={ivaDefault}
            metodoPago={metodoPago}
            onMetodoPagoChange={setMetodoPago}
            montoRecibido={montoRecibido}
            onMontoRecibidoChange={setMontoRecibido}
            cambio={cambio}
            esAbono={esAbono}
            onEsAbonoChange={setEsAbono}
            montoAbono={montoAbono}
            onMontoAbonoChange={setMontoAbono}
            errorPago={errorPago}
            cobrando={cobrando}
            onCobrar={cobrar}
            onLimpiar={limpiarCarrito}
          />
        )}
      </div>
    </div>
  )
}
