from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from auth import get_usuario_actual, UsuarioActual, get_db_tenant
from services.dashboard_service import calcular_kpis

router = APIRouter()


@router.get("/")
def dashboard(
    mes:     int = Query(None, ge=1, le=12),
    anio:    int = Query(None, ge=2020),
    db:      Session       = Depends(get_db_tenant),
    usuario: UsuarioActual = Depends(get_usuario_actual),
):
    ahora       = datetime.now(timezone.utc)
    mes_actual  = mes  or ahora.month
    anio_actual = anio or ahora.year
    return calcular_kpis(db, usuario.gym_id, mes_actual, anio_actual, usuario.es_admin)
