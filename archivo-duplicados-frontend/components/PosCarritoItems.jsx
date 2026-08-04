export default function PosCarritoItems({ carrito, onCambiarCantidad, onQuitar }) {
  return (
    <div className="carrito-items">
      {carrito.length === 0 ? (
        <p className="carrito-vacio">Selecciona productos del panel izquierdo</p>
      ) : (
        carrito.map(({ producto, cantidad }) => (
          <div key={producto.id} className="carrito-item">
            <div className="item-info">
              <span className="item-nombre">{producto.nombre}</span>
            </div>
            <div className="item-controles">
              <button className="btn-qty" onClick={() => onCambiarCantidad(producto.id, -1)}>−</button>
              <span className="item-qty num">{cantidad}</span>
              <button className="btn-qty" onClick={() => onCambiarCantidad(producto.id, +1)}>+</button>
            </div>
            <span className="item-subtotal num">${(producto.precio_venta * cantidad).toFixed(2)}</span>
            <button className="btn-quitar" onClick={() => onQuitar(producto.id)}>✕</button>
          </div>
        ))
      )}
    </div>
  )
}
