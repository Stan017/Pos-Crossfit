export default function PosPagoPanel({
  subtotal, montoIva, totalVenta, porcentajeIva, onPorcentajeIvaChange, ivaDefault,
  metodoPago, onMetodoPagoChange,
  montoRecibido, onMontoRecibidoChange, cambio,
  esAbono, onEsAbonoChange,
  montoAbono, onMontoAbonoChange,
  errorPago,
  cobrando, onCobrar, onLimpiar,
}) {
  return (
    <div className="carrito-pago">

      {/* IVA toggle */}
      <div className="pago-iva-row">
        <label className="iva-toggle">
          <input
            type="checkbox"
            checked={porcentajeIva > 0}
            onChange={e => onPorcentajeIvaChange(e.target.checked ? (ivaDefault || 15) : 0)}
          />
          <span>IVA</span>
        </label>
        {porcentajeIva > 0 && (
          <div className="iva-pct-input">
            <input
              type="number"
              min="0"
              max="100"
              step="0.1"
              value={porcentajeIva}
              onChange={e => onPorcentajeIvaChange(parseFloat(e.target.value) || 0)}
            />
            <span className="iva-pct-sym">%</span>
          </div>
        )}
      </div>

      {/* Desglose subtotal / IVA / total */}
      {porcentajeIva > 0 ? (
        <div className="pago-desglose">
          <div className="pago-linea">
            <span>Subtotal</span>
            <span className="num">${subtotal.toFixed(2)}</span>
          </div>
          <div className="pago-linea">
            <span>IVA ({porcentajeIva}%)</span>
            <span className="num">${montoIva.toFixed(2)}</span>
          </div>
          <div className="pago-linea pago-total-linea">
            <span>Total</span>
            <span className="num pago-total-valor">${totalVenta.toFixed(2)}</span>
          </div>
        </div>
      ) : (
        <div className="pago-total">
          <span>Total</span>
          <span className="num pago-total-valor">${totalVenta.toFixed(2)}</span>
        </div>
      )}

      {/* Método de pago */}
      <div className="pago-metodo">
        {['efectivo', 'transferencia'].map(m => (
          <button
            key={m}
            className={`btn-metodo ${metodoPago === m ? 'activo' : ''}`}
            onClick={() => onMetodoPagoChange(m)}
          >
            {m === 'efectivo' ? '💵 Efectivo' : '📲 Transferencia'}
          </button>
        ))}
      </div>

      {/* Monto recibido (solo efectivo y pago completo) */}
      {metodoPago === 'efectivo' && !esAbono && (
        <div className="pago-recibido">
          <label>
            <span className="label-text">Monto recibido</span>
            <input
              type="number"
              step="0.01"
              min={totalVenta}
              value={montoRecibido}
              onChange={e => onMontoRecibidoChange(e.target.value)}
              placeholder={`$${totalVenta.toFixed(2)}`}
            />
          </label>
          {cambio !== null && cambio >= 0 && (
            <div className="pago-cambio">
              <span>Cambio</span>
              <span className="num">${cambio.toFixed(2)}</span>
            </div>
          )}
        </div>
      )}

      {/* Tipo de cobro */}
      <div className="pago-tipo">
        <label className={`tipo-cobro ${!esAbono ? 'activo' : ''}`}>
          <input type="radio" checked={!esAbono} onChange={() => onEsAbonoChange(false)} />
          Pago completo
        </label>
        <label className={`tipo-cobro ${esAbono ? 'activo' : ''}`}>
          <input type="radio" checked={esAbono} onChange={() => onEsAbonoChange(true)} />
          Abono parcial
        </label>
      </div>

      {/* Monto del abono */}
      {esAbono && (
        <div className="pago-recibido">
          <label>
            <span className="label-text">Monto del abono</span>
            <input
              type="number"
              step="0.01"
              min="0"
              max={totalVenta}
              value={montoAbono}
              onChange={e => onMontoAbonoChange(e.target.value)}
              placeholder="$0.00"
            />
          </label>
          {montoAbono && (
            <div className="pago-cambio pago-saldo">
              <span>Saldo pendiente</span>
              <span className="num">${Math.max(0, totalVenta - parseFloat(montoAbono)).toFixed(2)}</span>
            </div>
          )}
        </div>
      )}

      {errorPago && <p className="form-error">{errorPago}</p>}

      <button
        className="btn-cobrar"
        onClick={onCobrar}
        disabled={cobrando || !!errorPago}
      >
        {cobrando ? 'Procesando...' : `Cobrar $${totalVenta.toFixed(2)}`}
      </button>

      <button className="btn-limpiar" onClick={onLimpiar}>
        Limpiar carrito
      </button>
    </div>
  )
}
