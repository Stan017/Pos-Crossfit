import { useState } from 'react'

// Navegación mes/año para vistas tipo Dashboard/Finanzas: arranca en el mes
// actual y no deja avanzar más allá de hoy.
export function useMonthNavigator() {
  const ahora = new Date()
  const [mes, setMes]   = useState(ahora.getMonth() + 1)   // 1-12
  const [anio, setAnio] = useState(ahora.getFullYear())

  const esMesActual = mes === ahora.getMonth() + 1 && anio === ahora.getFullYear()

  function retroceder() {
    if (mes === 1) { setMes(12); setAnio(a => a - 1) }
    else           { setMes(m => m - 1) }
  }

  function avanzar() {
    if (esMesActual) return
    if (mes === 12) { setMes(1); setAnio(a => a + 1) }
    else            { setMes(m => m + 1) }
  }

  return { mes, anio, esMesActual, retroceder, avanzar }
}
