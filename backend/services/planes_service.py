"""
Límite de staff por tier de plan (SaasTier), separado del ciclo de
facturación (SaasPlan) y del ciclo de vida de la suscripción (SaasEstado).

"Médico/coach" = fila activa en Instructor. "Asistente" = fila activa en
Usuario con rol=staff — el admin del gimnasio nunca cuenta para este límite,
es una cuenta aparte, no un cupo de staff.

Se llama antes de insertar la fila nueva en routes/instructores.py
(crear_instructor) y routes/usuarios.py (crear_usuario), no como un chequeo
retroactivo — un gimnasio que ya tiene más staff del que su tier permite hoy
(por ejemplo, después de un backfill de migración) no pierde nada existente,
simplemente no puede sumar uno más hasta que actualice su plan.
"""
from sqlalchemy.orm import Session
from fastapi import HTTPException, status

from models import Gimnasio, Instructor, Usuario, RolUsuario, SaasTier

TIER_LIMITES: dict[SaasTier, dict[str, int | None]] = {
    SaasTier.trial:         {"medicos": 5,  "asistentes": 1},
    SaasTier.solo:          {"medicos": 5,  "asistentes": 1},
    SaasTier.estandar:      {"medicos": 10, "asistentes": 2},
    SaasTier.clinica:       {"medicos": 15, "asistentes": 3},
    SaasTier.personalizado: {"medicos": None, "asistentes": None},
}


def verificar_limite_medicos(gimnasio: Gimnasio, db: Session) -> None:
    limite = TIER_LIMITES[gimnasio.saas_tier]["medicos"]
    if limite is None:
        return
    actuales = db.query(Instructor).filter(
        Instructor.gym_id == gimnasio.id,
        Instructor.activo == True,
    ).count()
    if actuales >= limite:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Tu plan {gimnasio.saas_tier.value} admite máximo {limite} médico(s)/coach(es). Actualizá tu plan para agregar más.",
        )


def verificar_limite_asistentes(gimnasio: Gimnasio, db: Session) -> None:
    limite = TIER_LIMITES[gimnasio.saas_tier]["asistentes"]
    if limite is None:
        return
    actuales = db.query(Usuario).filter(
        Usuario.gym_id == gimnasio.id,
        Usuario.rol    == RolUsuario.staff,
        Usuario.activo == True,
    ).count()
    if actuales >= limite:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Tu plan {gimnasio.saas_tier.value} admite máximo {limite} asistente(s). Actualizá tu plan para agregar más.",
        )
