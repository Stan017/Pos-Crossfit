import { describe, it, expect } from 'vitest'
import {
  fmtMetodoPago,
  estadoMembresiaBadge,
  estadoSaasBadge,
  fmtPlanSaas,
  fmtTierSaas,
  fmtEstadoPagoSaas,
} from './formato.js'

describe('fmtMetodoPago', () => {
  it('mapea los tres métodos conocidos', () => {
    expect(fmtMetodoPago('transferencia')).toBe('Transferencia')
    expect(fmtMetodoPago('tarjeta')).toBe('Tarjeta')
    expect(fmtMetodoPago('efectivo')).toBe('Efectivo')
  })

  it('cualquier valor desconocido cae a Efectivo (el default del negocio)', () => {
    expect(fmtMetodoPago(undefined)).toBe('Efectivo')
    expect(fmtMetodoPago('bitcoin')).toBe('Efectivo')
  })
})

describe('estadoMembresiaBadge', () => {
  it('devuelve label y clase para cada estado real del backend', () => {
    expect(estadoMembresiaBadge('activa')).toEqual({ label: 'Activa', clase: 'badge-ok' })
    expect(estadoMembresiaBadge('por_vencer')).toEqual({ label: 'Por vencer', clase: 'badge-warning' })
    expect(estadoMembresiaBadge('critica')).toEqual({ label: 'Crítica', clase: 'badge-danger' })
    expect(estadoMembresiaBadge('vencida')).toEqual({ label: 'Vencida', clase: 'badge-inactivo' })
    expect(estadoMembresiaBadge('pendiente_pago')).toEqual({ label: 'Pendiente pago', clase: 'badge-warning' })
    expect(estadoMembresiaBadge('cancelada')).toEqual({ label: 'Cancelada', clase: 'badge-inactivo' })
  })

  it('un estado desconocido no rompe la UI: lo muestra crudo con badge neutro', () => {
    expect(estadoMembresiaBadge('estado_nuevo')).toEqual({ label: 'estado_nuevo', clase: 'badge-inactivo' })
  })
})

describe('estadoSaasBadge', () => {
  it('cubre los seis estados SaaS', () => {
    expect(estadoSaasBadge('trial').label).toBe('Prueba')
    expect(estadoSaasBadge('activa').clase).toBe('badge-ok')
    expect(estadoSaasBadge('por_vencer').clase).toBe('badge-warning')
    expect(estadoSaasBadge('en_gracia').clase).toBe('badge-danger')
    expect(estadoSaasBadge('vencida').clase).toBe('badge-inactivo')
    expect(estadoSaasBadge('suspendida').clase).toBe('badge-inactivo')
  })
})

describe('fmtPlanSaas', () => {
  it('mapea los cuatro períodos reales de SaasPlan', () => {
    expect(fmtPlanSaas('mensual')).toBe('Mensual')
    expect(fmtPlanSaas('trimestral')).toBe('Trimestral')
    expect(fmtPlanSaas('semestral')).toBe('Semestral')
    expect(fmtPlanSaas('anual')).toBe('Anual')
  })

  it('trial (y cualquier otro valor) se muestra como Prueba', () => {
    expect(fmtPlanSaas('trial')).toBe('Prueba')
    expect(fmtPlanSaas(null)).toBe('Prueba')
  })
})

describe('fmtTierSaas', () => {
  it('mapea los cinco tiers', () => {
    expect(fmtTierSaas('trial')).toBe('Prueba')
    expect(fmtTierSaas('solo')).toBe('Solo')
    expect(fmtTierSaas('estandar')).toBe('Estándar')
    expect(fmtTierSaas('clinica')).toBe('Clínica')
    expect(fmtTierSaas('personalizado')).toBe('Personalizado')
  })

  it('un tier futuro que el frontend no conoce se muestra crudo, no undefined', () => {
    expect(fmtTierSaas('enterprise')).toBe('enterprise')
  })
})

describe('fmtEstadoPagoSaas', () => {
  it('cubre pendiente/confirmado/rechazado y el fallback', () => {
    expect(fmtEstadoPagoSaas('pendiente')).toEqual({ label: 'Pendiente', clase: 'badge-warning' })
    expect(fmtEstadoPagoSaas('confirmado')).toEqual({ label: 'Confirmado', clase: 'badge-ok' })
    expect(fmtEstadoPagoSaas('rechazado')).toEqual({ label: 'Rechazado', clase: 'badge-danger' })
    expect(fmtEstadoPagoSaas('otro')).toEqual({ label: 'otro', clase: 'badge-inactivo' })
  })
})
