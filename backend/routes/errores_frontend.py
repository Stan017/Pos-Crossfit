import logging

from fastapi import APIRouter, Request
from pydantic import BaseModel, Field

from limiter import limiter

logger = logging.getLogger("crossfit_saas")

router = APIRouter()


class ErrorFrontendIn(BaseModel):
    mensaje:  str            = Field(..., max_length=2000)
    stack:    str | None     = Field(None, max_length=5000)
    url:      str            = Field(..., max_length=500)
    # 'react-error-boundary' | 'window-error' | 'unhandled-rejection'
    contexto: str | None     = Field(None, max_length=100)


@router.post("", status_code=204)
@limiter.limit("10/minute")
async def reportar_error_frontend(request: Request, body: ErrorFrontendIn):
    """
    Sin auth: un crash puede pasar antes de loguearse (ej. la pantalla de
    Login). Solo loguea junto con el resto de logs del backend — no hay
    tabla en la DB, es diagnóstico operativo, no dato de negocio de un gym.
    """
    logger.error(
        "Error frontend [%s] url=%s: %s\n%s",
        body.contexto or "desconocido", body.url, body.mensaje, body.stack or "(sin stack)",
    )
