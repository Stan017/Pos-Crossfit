// El backend devuelve fechas "YYYY-MM-DD" sin hora. new Date() interpreta
// eso como medianoche UTC, y Ecuador es UTC-5 — sin el 'T00:00:00', un
// usuario local ve la fecha corrida un día para atrás.
export function parseFechaLocal(iso) {
  return new Date(iso + 'T00:00:00')
}

// "Hoy" en la fecha calendario LOCAL del usuario, no en UTC. new Date().
// toISOString() da la fecha UTC — en Ecuador (UTC-5), desde las 19:00
// hora local esa fecha UTC ya es el día siguiente, así que "hoy" mostraría
// el día equivocado durante 5 horas cada noche.
export function hoyLocal() {
  const d   = new Date()
  const mes = String(d.getMonth() + 1).padStart(2, '0')
  const dia = String(d.getDate()).padStart(2, '0')
  return `${d.getFullYear()}-${mes}-${dia}`
}

export const MESES = [
  'enero','febrero','marzo','abril','mayo','junio',
  'julio','agosto','septiembre','octubre','noviembre','diciembre'
]

export function formatFecha(iso) {
  if (!iso) return '—'
  return parseFechaLocal(iso).toLocaleDateString('es-EC', {
    day: '2-digit', month: 'short', year: 'numeric',
  })
}

// Para timestamps completos (con hora y timezone explícitos en el string).
// No necesita el parche de formatFecha() porque el offset ya viene incluido.
export function formatFechaHora(iso) {
  if (!iso) return '—'
  return new Date(iso).toLocaleString('es-EC', {
    day: '2-digit', month: 'short', year: 'numeric',
    hour: '2-digit', minute: '2-digit',
  })
}
