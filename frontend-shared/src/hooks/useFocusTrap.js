import { useEffect, useRef } from 'react'

const SELECTOR_FOCUSABLE =
  'a[href], button:not([disabled]), textarea:not([disabled]), input:not([disabled]), select:not([disabled]), [tabindex]:not([tabindex="-1"])'

// Atrapa el foco de teclado dentro del modal mientras `abierto` es true —
// Tab/Shift+Tab ciclan entre los elementos enfocables del modal en vez de
// escaparse al fondo de la página — y lo devuelve al elemento que tenía el
// foco antes de abrirse, al cerrarse. Devuelve un ref para poner en el
// contenedor del modal (el div.modal, no el overlay).
export function useFocusTrap(abierto) {
  const ref = useRef(null)

  useEffect(() => {
    if (!abierto) return
    const contenedor = ref.current
    if (!contenedor) return

    const previamenteEnfocado = document.activeElement

    function focosDisponibles() {
      return Array.from(contenedor.querySelectorAll(SELECTOR_FOCUSABLE))
        .filter(el => el.offsetParent !== null)
    }

    const primerFoco = focosDisponibles()[0]
    ;(primerFoco ?? contenedor).focus()

    function onKeyDown(e) {
      if (e.key !== 'Tab') return
      const focos = focosDisponibles()
      if (focos.length === 0) { e.preventDefault(); return }
      const primero = focos[0]
      const ultimo  = focos[focos.length - 1]
      if (e.shiftKey && document.activeElement === primero) {
        e.preventDefault()
        ultimo.focus()
      } else if (!e.shiftKey && document.activeElement === ultimo) {
        e.preventDefault()
        primero.focus()
      }
    }

    contenedor.addEventListener('keydown', onKeyDown)
    return () => {
      contenedor.removeEventListener('keydown', onKeyDown)
      if (previamenteEnfocado?.focus) previamenteEnfocado.focus()
    }
  }, [abierto])

  return ref
}
