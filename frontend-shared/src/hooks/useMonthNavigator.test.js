import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest'
import { renderHook, act } from '@testing-library/react'
import { useMonthNavigator } from './useMonthNavigator.js'

describe('useMonthNavigator', () => {
  beforeEach(() => {
    vi.useFakeTimers()
    vi.setSystemTime(new Date(2026, 5, 15)) // 15 de junio de 2026
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  it('arranca en el mes y año actuales, marcado como mes actual', () => {
    const { result } = renderHook(() => useMonthNavigator())
    expect(result.current.mes).toBe(6)
    expect(result.current.anio).toBe(2026)
    expect(result.current.esMesActual).toBe(true)
  })

  it('retroceder resta un mes y deja de ser "mes actual"', () => {
    const { result } = renderHook(() => useMonthNavigator())
    act(() => result.current.retroceder())
    expect(result.current.mes).toBe(5)
    expect(result.current.anio).toBe(2026)
    expect(result.current.esMesActual).toBe(false)
  })

  it('retroceder desde enero cruza al diciembre del año anterior', () => {
    vi.setSystemTime(new Date(2026, 0, 10)) // enero 2026
    const { result } = renderHook(() => useMonthNavigator())
    act(() => result.current.retroceder())
    expect(result.current.mes).toBe(12)
    expect(result.current.anio).toBe(2025)
  })

  it('avanzar no deja pasar del mes actual (no hay dashboard del futuro)', () => {
    const { result } = renderHook(() => useMonthNavigator())
    act(() => result.current.avanzar())
    expect(result.current.mes).toBe(6)
    expect(result.current.anio).toBe(2026)
  })

  it('avanzar funciona una vez que se retrocedió, y cruza diciembre->enero', () => {
    vi.setSystemTime(new Date(2026, 0, 10)) // enero 2026
    const { result } = renderHook(() => useMonthNavigator())
    act(() => result.current.retroceder()) // diciembre 2025
    expect(result.current.mes).toBe(12)
    act(() => result.current.avanzar()) // de vuelta a enero 2026
    expect(result.current.mes).toBe(1)
    expect(result.current.anio).toBe(2026)
    expect(result.current.esMesActual).toBe(true)
  })
})
