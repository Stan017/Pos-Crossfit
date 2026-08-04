import { describe, it, expect } from 'vitest'
import { parseFechaLocal, hoyLocal, MESES, formatFecha, formatFechaHora } from './fecha.js'

describe('parseFechaLocal', () => {
  it('interpreta YYYY-MM-DD como medianoche LOCAL, no UTC (el bug del día corrido)', () => {
    // Sin el parche, en UTC-5 el 2026-01-15 se vería como 14 de enero.
    const d = parseFechaLocal('2026-01-15')
    expect(d.getFullYear()).toBe(2026)
    expect(d.getMonth()).toBe(0)
    expect(d.getDate()).toBe(15)
    expect(d.getHours()).toBe(0)
  })
})

describe('hoyLocal', () => {
  it('devuelve YYYY-MM-DD con la fecha calendario local de hoy', () => {
    const hoy = hoyLocal()
    expect(hoy).toMatch(/^\d{4}-\d{2}-\d{2}$/)
    const ahora = new Date()
    expect(hoy).toBe(
      `${ahora.getFullYear()}-${String(ahora.getMonth() + 1).padStart(2, '0')}-${String(ahora.getDate()).padStart(2, '0')}`
    )
  })

  it('ida y vuelta con parseFechaLocal cae en el día de hoy', () => {
    expect(parseFechaLocal(hoyLocal()).getDate()).toBe(new Date().getDate())
  })
})

describe('MESES', () => {
  it('tiene los 12 meses en orden', () => {
    expect(MESES).toHaveLength(12)
    expect(MESES[0]).toBe('enero')
    expect(MESES[11]).toBe('diciembre')
  })
})

describe('formatFecha', () => {
  it('null o vacío se muestra como raya, no como Invalid Date', () => {
    expect(formatFecha(null)).toBe('—')
    expect(formatFecha('')).toBe('—')
    expect(formatFecha(undefined)).toBe('—')
  })

  it('formatea sin correr el día para atrás', () => {
    const out = formatFecha('2026-08-04')
    expect(out).toContain('04')
    expect(out).toContain('2026')
    expect(out).not.toContain('03')
  })
})

describe('formatFechaHora', () => {
  it('null se muestra como raya', () => {
    expect(formatFechaHora(null)).toBe('—')
  })

  it('un timestamp con offset explícito incluye fecha y hora', () => {
    const out = formatFechaHora('2026-08-04T12:30:00+00:00')
    expect(out).toContain('2026')
    expect(out).toMatch(/\d{2}:\d{2}/)
  })
})
