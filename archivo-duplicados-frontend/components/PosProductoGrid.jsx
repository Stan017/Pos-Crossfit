export default function PosProductoGrid({ productos, busqueda, onBusquedaChange, cargando, carrito, onAgregar }) {
  return (
    <div className="pos-productos">
      <input
        className="pos-busqueda"
        type="text"
        placeholder="Buscar producto..."
        value={busqueda}
        onChange={e => onBusquedaChange(e.target.value)}
        autoFocus
      />

      {cargando ? (
        <div className="pos-grilla">
          {Array.from({ length: 12 }).map((_, i) => (
            <div key={i} className="pos-card pos-card-skeleton" aria-hidden="true">
              <div className="skel skel-img" />
              <div className="skel skel-txt" />
              <div className="skel skel-txt2" />
            </div>
          ))}
        </div>
      ) : productos.length === 0 ? (
        <p className="pos-vacio">
          {busqueda ? 'Sin resultados.' : 'No hay productos con stock disponible.'}
        </p>
      ) : (
        <div className="pos-grilla">
          {productos.map(p => {
            const enCarrito = carrito.find(i => i.producto.id === p.id)
            return (
              <button
                key={p.id}
                className={`pos-card ${enCarrito ? 'en-carrito' : ''} ${p.imagen_url ? 'pos-card-con-img' : ''}`}
                onClick={() => onAgregar(p)}
              >
                {enCarrito && (
                  <span className="pos-card-qty">{enCarrito.cantidad}</span>
                )}
                {p.imagen_url
                  ? <img src={p.imagen_url} alt={p.nombre} className="pos-card-img" loading="lazy" onError={e => { e.target.style.display = 'none' }} />
                  : <span className="pos-card-img-placeholder">📦</span>
                }
                <span className="pos-card-nombre">{p.nombre}</span>
                <span className="pos-card-precio num">${p.precio_venta.toFixed(2)}</span>
                <span className={`pos-card-stock ${p.stock <= 3 ? 'stock-bajo' : ''}`}>
                  Stock: {p.stock}
                </span>
              </button>
            )
          })}
        </div>
      )}
    </div>
  )
}
