"""
Rutas de analíticas de plataforma para el superadmin (frontend-admin/). La
lógica (queries, cálculo) vive en services/admin_analytics_service.py — acá
solo autenticación, rate limit y despacho.

IMPORTANTE: cada ruta acá necesita su propio @limiter.limit(...) — a
diferencia de require_platform_admin (auth), slowapi no tiene forma de
aplicar el rate-limit una sola vez a nivel de router acá, así que toda ruta
nueva en este archivo tiene que agregarlo a mano (mismo criterio que
admin_router en suscripciones.py). Olvidarlo deja la clave de plataforma
abierta a fuerza bruta sin límite en esa ruta puntual.
"""
from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from database import get_db_platform
from platform_admin import require_platform_admin
from services.admin_analytics_service import calcular_analytics_por_gym, calcular_resumen_plataforma
from limiter import limiter

router = APIRouter(dependencies=[Depends(require_platform_admin)])


@router.get("/gyms")
@limiter.limit("20/minute")
def analytics_por_gym(request: Request, db: Session = Depends(get_db_platform)):
    """Una fila por gym con staff, instructores por tipo, miembros, ventas del mes y actividad."""
    return calcular_analytics_por_gym(db)


@router.get("/resumen")
@limiter.limit("20/minute")
def analytics_resumen(request: Request, db: Session = Depends(get_db_platform)):
    """Totales de toda la plataforma."""
    return calcular_resumen_plataforma(db)


@router.get("/ping")
@limiter.limit("20/minute")
def ping(request: Request):
    """Valida la X-Platform-Key sin devolver datos — usado por el login de frontend-admin/."""
    return {"ok": True}
