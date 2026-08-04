import { useState, useEffect, useRef } from 'react'
import { miembrosAPI } from '../services/api'
import IconoNuevoCliente from './IconoNuevoCliente'

const FORM_CLIENTE_VACIO = { nombre: '', apellido: '', telefono: '' }

// Autocontenido: búsqueda de cliente, sugeridos, y alta rápida. El padre solo
// se entera del cliente ya elegido — toda la búsqueda/formulario en vuelo es
// estado interno que no le interesa a POS.jsx.
export default function PosClienteSelector({ cliente, onSeleccionarCliente, onQuitarCliente }) {
  const [busquedaCliente, setBusquedaCliente]   = useState('')
  const [sugeridos, setSugeridos]               = useState([])
  const [mostrarSugeridos, setMostrarSugeridos] = useState(false)
  const [registrandoCliente, setRegistrandoCliente] = useState(false)
  const [formCliente, setFormCliente]           = useState(FORM_CLIENTE_VACIO)
  const [guardandoCliente, setGuardandoCliente] = useState(false)
  const clienteRef = useRef(null)

  useEffect(() => {
    if (!busquedaCliente.trim()) { setSugeridos([]); return }
    const t = setTimeout(async () => {
      try {
        const res = await miembrosAPI.listar({ q: busquedaCliente })
        setSugeridos(res.data.slice(0, 6))
        setMostrarSugeridos(true)
      } catch { setSugeridos([]) }
    }, 250)
    return () => clearTimeout(t)
  }, [busquedaCliente])

  function seleccionar(c) {
    onSeleccionarCliente(c)
    setBusquedaCliente('')
    setSugeridos([])
    setMostrarSugeridos(false)
    setRegistrandoCliente(false)
  }

  // Cerrar sugeridos al clicar fuera
  useEffect(() => {
    function handler(e) {
      if (clienteRef.current && !clienteRef.current.contains(e.target)) {
        setMostrarSugeridos(false)
      }
    }
    document.addEventListener('mousedown', handler)
    return () => document.removeEventListener('mousedown', handler)
  }, [])

  async function registrarClienteRapido(e) {
    e.preventDefault()
    if (!formCliente.nombre.trim()) return
    try {
      setGuardandoCliente(true)
      const res = await miembrosAPI.crear({
        nombre:   formCliente.nombre.trim(),
        apellido: formCliente.apellido.trim() || '—',
        telefono: formCliente.telefono.trim() || null,
      })
      seleccionar(res.data)
      setFormCliente(FORM_CLIENTE_VACIO)
    } catch {
      alert('No se pudo registrar el cliente.')
    } finally {
      setGuardandoCliente(false)
    }
  }

  return (
    <div className="carrito-cliente" ref={clienteRef}>
      {cliente ? (
        <div className="cliente-seleccionado">
          <span>👤 {cliente.nombre} {cliente.apellido ?? ''}</span>
          <button className="btn-quitar-cliente" onClick={onQuitarCliente}>✕</button>
        </div>
      ) : (
        <div className="cliente-buscar">
          <div className="cliente-buscar-row">
            <input
              className="input-cliente"
              type="text"
              placeholder="Buscar cliente..."
              value={busquedaCliente}
              onChange={e => { setBusquedaCliente(e.target.value); setMostrarSugeridos(true) }}
              onFocus={() => busquedaCliente && setMostrarSugeridos(true)}
            />
            <button
              type="button"
              className="btn-nuevo-cliente"
              title="Registrar nuevo cliente"
              onClick={() => {
                setFormCliente({ nombre: busquedaCliente.trim(), apellido: '', telefono: '' })
                setRegistrandoCliente(true)
                setMostrarSugeridos(false)
              }}
            >
              <IconoNuevoCliente size={24} />
            </button>
          </div>
          {mostrarSugeridos && (busquedaCliente.trim()) && (
            <div className="cliente-dropdown">
              {sugeridos.map(c => (
                <button key={c.id} className="cliente-opcion" onClick={() => seleccionar(c)}>
                  <span>{c.nombre} {c.apellido ?? ''}</span>
                  {c.telefono && <span className="cliente-tel">{c.telefono}</span>}
                </button>
              ))}
              <button
                className="cliente-opcion cliente-nuevo"
                onClick={() => { setRegistrandoCliente(true); setMostrarSugeridos(false) }}
              >
                + Registrar "{busquedaCliente}"
              </button>
            </div>
          )}
        </div>
      )}

      {registrandoCliente && (
        <form className="registro-rapido" onSubmit={registrarClienteRapido}>
          <p className="registro-titulo">Nuevo cliente</p>
          <input
            placeholder="Nombre *"
            value={formCliente.nombre}
            onChange={e => setFormCliente(p => ({ ...p, nombre: e.target.value }))}
            required
          />
          <input
            placeholder="Apellido"
            value={formCliente.apellido}
            onChange={e => setFormCliente(p => ({ ...p, apellido: e.target.value }))}
          />
          <input
            placeholder="Teléfono"
            value={formCliente.telefono}
            onChange={e => setFormCliente(p => ({ ...p, telefono: e.target.value }))}
          />
          <div className="registro-acciones">
            <button type="button" className="btn btn-sm btn-outline"
              onClick={() => setRegistrandoCliente(false)}>Cancelar</button>
            <button type="submit" className="btn btn-sm btn-primary" disabled={guardandoCliente}>
              {guardandoCliente ? '...' : 'Guardar'}
            </button>
          </div>
        </form>
      )}
    </div>
  )
}
