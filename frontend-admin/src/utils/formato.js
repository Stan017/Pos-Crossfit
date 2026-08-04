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

export function fmtVertical(v) {
  return v === 'medico' ? 'Clínica' : 'CrossFit'
}

export function fmtEstadoPagoSaas(estado) {
  const map = {
    pendiente:  { label: 'Pendiente',  clase: 'badge-warning'  },
    confirmado: { label: 'Confirmado', clase: 'badge-ok'       },
    rechazado:  { label: 'Rechazado',  clase: 'badge-danger'   },
  }
  return map[estado] || { label: estado, clase: 'badge-inactivo' }
}

export function formatFecha(iso) {
  if (!iso) return '—'
  return new Date(iso + 'T00:00:00').toLocaleDateString('es-EC', {
    day: '2-digit', month: 'short', year: 'numeric',
  })
}

export function formatFechaHora(iso) {
  if (!iso) return '—'
  return new Date(iso).toLocaleString('es-EC', {
    day: '2-digit', month: 'short', year: 'numeric',
    hour: '2-digit', minute: '2-digit',
  })
}
