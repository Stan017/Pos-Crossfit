import '@testing-library/jest-dom/vitest'

// jsdom no calcula layout: offsetParent es siempre null ahí, sin importar
// visibilidad real. useFocusTrap usa offsetParent !== null para filtrar
// elementos ocultos — sin este stub, TODO se ve "oculto" en los tests y el
// trap de foco nunca encuentra nada. display:none real sigue funcionando
// porque jsdom sí refleja eso en el árbol.
Object.defineProperty(HTMLElement.prototype, 'offsetParent', {
  get() {
    return this.parentNode
  },
})
