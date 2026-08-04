export function fmtMetodoPago(m) {
  if (m === 'transferencia') return 'Transferencia'
  if (m === 'tarjeta')       return 'Tarjeta'
  return 'Efectivo'
}

export function estadoMembresiaBadge(estado) {
  const map = {
    activa:         { label: 'Activa',         clase: 'badge-ok'       },
    por_vencer:     { label: 'Por vencer',     clase: 'badge-warning'  },
    critica:        { label: 'Crítica',        clase: 'badge-danger'   },
    vencida:        { label: 'Vencida',        clase: 'badge-inactivo' },
    pendiente_pago: { label: 'Pendiente pago', clase: 'badge-warning'  },
    cancelada:      { label: 'Cancelada',      clase: 'badge-inactivo' },
  }
  return map[estado] || { label: estado, clase: 'badge-inactivo' }
}

export function estadoSaasBadge(estado) {
  const map = {
    trial:      { label: 'Prueba',      clase: 'badge-sin-plan' },
    activa:     { label: 'Activa',      clase: 'badge-ok'       },
    por_vencer: { label: 'Por vencer',  clase: 'badge-warning'  },
    en_gracia:  { label: 'En gracia',   clase: 'badge-danger'   },
    vencida:    { label: 'Vencida',     clase: 'badge-inactivo' },
    suspendida: { label: 'Suspendida',  clase: 'badge-inactivo' },
  }
  return map[estado] || { label: estado, clase: 'badge-inactivo' }
}

export function fmtPlanSaas(p) {
  if (p === 'mensual')    return 'Mensual'
  if (p === 'trimestral') return 'Trimestral'
  if (p === 'semestral')  return 'Semestral'
  if (p === 'anual')      return 'Anual'
  return 'Prueba'
}

export function fmtTierSaas(t) {
  const map = { trial: 'Prueba', solo: 'Solo', estandar: 'Estándar', clinica: 'Clínica', personalizado: 'Personalizado' }
  return map[t] ?? t
}

export function fmtEstadoPagoSaas(estado) {
  const map = {
    pendiente:  { label: 'Pendiente',  clase: 'badge-warning'  },
    confirmado: { label: 'Confirmado', clase: 'badge-ok'       },
    rechazado:  { label: 'Rechazado',  clase: 'badge-danger'   },
  }
  return map[estado] || { label: estado, clase: 'badge-inactivo' }
}
