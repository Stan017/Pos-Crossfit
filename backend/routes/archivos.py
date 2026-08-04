import os
import re

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse

from auth import get_usuario_actual, UsuarioActual
from storage import DIR_STATIC, CARPETAS_VALIDAS

router = APIRouter()

# uuid4().hex + extensión — cualquier otra cosa (../, rutas, etc.) se rechaza
_NOMBRE_VALIDO = re.compile(r"^[0-9a-f]{32}\.(jpg|png)$")


@router.get("/{carpeta}/{gym_id}/{nombre}")
def servir_archivo(
    carpeta: str,
    gym_id:  str,
    nombre:  str,
    usuario: UsuarioActual = Depends(get_usuario_actual),
):
    if carpeta not in CARPETAS_VALIDAS or not _NOMBRE_VALIDO.match(nombre):
        raise HTTPException(status_code=404, detail="Archivo no encontrado.")

    # El gym_id de la URL tiene que ser el del usuario logueado — así es como
    # se evita que un gym vea los comprobantes/fotos de otro gym.
    if gym_id != str(usuario.gym_id):
        raise HTTPException(status_code=403, detail="No autorizado.")

    ruta = os.path.join(DIR_STATIC, carpeta, gym_id, nombre)
    if not os.path.isfile(ruta):
        raise HTTPException(status_code=404, detail="Archivo no encontrado.")

    return FileResponse(ruta)
