"""
Guardado de archivos subidos por el usuario (comprobantes de pago, fotos de
producto). Usa Supabase Storage (bucket privado, mismo proyecto que la DB) vía
su API REST — sin SDK nuevo, solo urllib.request (stdlib), autenticado con
SUPABASE_SERVICE_ROLE_KEY. El bucket es privado a propósito: si fuera público,
cualquiera con la URL se saltearía el chequeo de "este comprobante es de tu
gym" que vive en routes/archivos.py — con bucket privado, solo el backend (que
tiene la service key) puede leerlo, y el control de acceso real sigue siendo
nuestro endpoint autenticado.

Los archivos se identifican por gym_id dentro del bucket y se sirven a través
de GET /archivos/{carpeta}/{gym_id}/{nombre} (routes/archivos.py), que exige
estar autenticado y que el gym_id de la URL matchee el del usuario.
"""
import json
import os
import urllib.error
import urllib.request
import uuid

from fastapi import HTTPException, UploadFile

# Magic numbers reales de cada formato — el Content-Type que manda el cliente
# es un header que cualquiera puede mentir, esto mira los bytes de verdad.
_FIRMAS = {
    b"\xff\xd8\xff":         "jpg",
    b"\x89PNG\r\n\x1a\n":    "png",
}
_CONTENT_TYPE = {"jpg": "image/jpeg", "png": "image/png"}

CARPETAS_VALIDAS = {"comprobantes", "productos"}

SUPABASE_URL               = os.getenv("SUPABASE_URL", "")
SUPABASE_SERVICE_ROLE_KEY  = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")
SUPABASE_STORAGE_BUCKET    = os.getenv("SUPABASE_STORAGE_BUCKET", "archivos")


def _object_url(path: str) -> str:
    return f"{SUPABASE_URL}/storage/v1/object/{SUPABASE_STORAGE_BUCKET}/{path}"


def guardar_imagen(carpeta: str, gym_id: str, archivo: UploadFile) -> str:
    """
    Sube una imagen jpg/png del gym a Supabase Storage y devuelve la URL para
    pedirla vía /archivos. El tipo se determina por los bytes reales del
    archivo (magic number), no por el Content-Type que manda el cliente en el
    multipart — ese header lo puede poner cualquier cosa quien suba el
    archivo, no certifica nada sobre el contenido real.
    """
    contenido = archivo.file.read()
    extension = next(
        (ext for firma, ext in _FIRMAS.items() if contenido.startswith(firma)),
        None,
    )
    if extension is None:
        raise HTTPException(status_code=400, detail="Solo se aceptan imágenes JPG o PNG.")

    nombre = f"{uuid.uuid4().hex}.{extension}"
    path   = f"{carpeta}/{gym_id}/{nombre}"

    req = urllib.request.Request(
        _object_url(path),
        data=contenido,
        method="POST",
        headers={
            "Authorization": f"Bearer {SUPABASE_SERVICE_ROLE_KEY}",
            "Content-Type":  _CONTENT_TYPE[extension],
        },
    )
    try:
        urllib.request.urlopen(req, timeout=15)
    except (urllib.error.HTTPError, urllib.error.URLError) as e:
        raise HTTPException(status_code=502, detail="No se pudo guardar el archivo.") from e

    return f"/archivos/{carpeta}/{gym_id}/{nombre}"


def _es_error_no_encontrado(e: urllib.error.HTTPError) -> bool:
    # La API de Storage de Supabase NO usa 404 para "objeto no encontrado" —
    # devuelve HTTP 400 con el código real embebido en el body JSON
    # ({"statusCode":"404","error":"not_found",...}). Confirmado a mano contra
    # el bucket real: un GET/DELETE a un objeto inexistente vuelve 400, nunca
    # 404. Si algún día cambian el contrato, esto cae al 502 genérico de abajo
    # en vez de mentir con un 404 — más seguro que asumir el body.
    try:
        cuerpo = json.loads(e.read())
        return cuerpo.get("statusCode") == "404" or cuerpo.get("error") == "not_found"
    except (ValueError, json.JSONDecodeError):
        return False


def obtener_archivo(carpeta: str, gym_id: str, nombre: str) -> tuple[bytes, str]:
    """
    Trae los bytes de un archivo desde Supabase Storage. Caller:
    routes/archivos.py, después de validar auth + que el gym_id matchee al
    usuario logueado — acá ya no se vuelve a chequear nada de eso, es solo I/O.
    """
    path = f"{carpeta}/{gym_id}/{nombre}"
    req = urllib.request.Request(
        _object_url(path),
        headers={"Authorization": f"Bearer {SUPABASE_SERVICE_ROLE_KEY}"},
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return resp.read(), resp.headers.get("Content-Type", "application/octet-stream")
    except urllib.error.HTTPError as e:
        if e.code == 404 or _es_error_no_encontrado(e):
            raise HTTPException(status_code=404, detail="Archivo no encontrado.") from e
        raise HTTPException(status_code=502, detail="No se pudo obtener el archivo.") from e


def borrar_archivo(url: str) -> None:
    """
    Borra un archivo a partir de la URL que devolvió guardar_imagen(). Best-effort:
    si la URL no tiene el formato esperado o el archivo ya no existe, no hace nada.
    Caller: cuando falla el commit que iba a referenciar el archivo recién guardado
    (queda huérfano) o cuando se reemplaza un archivo existente por uno nuevo.
    """
    partes = url.strip("/").split("/")  # ["archivos", carpeta, gym_id, nombre]
    if len(partes) != 4 or partes[0] != "archivos":
        return
    _, carpeta, gym_id, nombre = partes
    path = f"{carpeta}/{gym_id}/{nombre}"

    req = urllib.request.Request(
        _object_url(path),
        method="DELETE",
        headers={"Authorization": f"Bearer {SUPABASE_SERVICE_ROLE_KEY}"},
    )
    try:
        urllib.request.urlopen(req, timeout=15)
    except urllib.error.URLError:
        pass
