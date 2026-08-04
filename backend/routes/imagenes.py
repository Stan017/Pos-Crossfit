from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile
from sqlalchemy.orm import Session
from models import Producto
from auth import require_admin, UsuarioActual, get_db_tenant
from storage import guardar_imagen, borrar_archivo
from limiter import limiter

router = APIRouter()


@router.post("/{producto_id}/imagen")
@limiter.limit("20/minute")
def subir_imagen_producto(
    request:     Request,
    producto_id: int,
    file:        UploadFile     = File(...),
    db:          Session        = Depends(get_db_tenant),
    usuario:     UsuarioActual  = Depends(require_admin),
):
    producto = db.query(Producto).filter(
        Producto.id     == producto_id,
        Producto.gym_id == usuario.gym_id,
    ).first()
    if not producto:
        raise HTTPException(status_code=404, detail="Producto no encontrado.")

    url_anterior = producto.imagen_url
    nueva_url    = guardar_imagen("productos", str(usuario.gym_id), file)
    producto.imagen_url = nueva_url

    try:
        db.commit()
    except Exception:
        borrar_archivo(nueva_url)
        raise

    if url_anterior:
        borrar_archivo(url_anterior)

    return {"imagen_url": producto.imagen_url}
