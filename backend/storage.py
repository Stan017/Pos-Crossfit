"""
Guardado de archivos subidos por el usuario (comprobantes de pago, fotos de
producto). Hoy guarda en disco local del servidor — es la única implementación
que existe en el proyecto. Al hacer deploy, si migra a Supabase Storage o
DigitalOcean Spaces, se cambia únicamente este archivo: ningún endpoint que
llama a guardar_imagen() necesita tocarse.

Los archivos se guardan separados por gym_id en disco y se sirven a través de
GET /archivos/{carpeta}/{gym_id}/{nombre} (routes/archivos.py), que exige estar
autenticado y que el gym_id de la URL matchee el del usuario — no van sueltos
en un mount público sin auth.
"""
import os
import uuid

from fastapi import HTTPException, UploadFile

# Magic numbers reales de cada formato — el Content-Type que manda el cliente
# es un header cualquiera puede mentir, esto mira los bytes de verdad.
_FIRMAS = {
    b"\xff\xd8\xff":         "jpg",
    b"\x89PNG\r\n\x1a\n":    "png",
}

CARPETAS_VALIDAS = {"comprobantes", "productos"}

BASE_DIR   = os.path.dirname(os.path.abspath(__file__))
DIR_STATIC = os.path.join(BASE_DIR, "static")


def guardar_imagen(carpeta: str, gym_id: str, archivo: UploadFile) -> str:
    """
    Guarda una imagen jpg/png del gym y devuelve la URL para pedirla vía /archivos.
    El tipo se determina por los bytes reales del archivo (magic number), no por el
    Content-Type que manda el cliente en el multipart — ese header lo puede poner
    cualquier cosa quien suba el archivo, no certifica nada sobre el contenido real.
    """
    contenido = archivo.file.read()
    extension = next(
        (ext for firma, ext in _FIRMAS.items() if contenido.startswith(firma)),
        None,
    )
    if extension is None:
        raise HTTPException(status_code=400, detail="Solo se aceptan imágenes JPG o PNG.")

    destino_dir = os.path.join(DIR_STATIC, carpeta, gym_id)
    os.makedirs(destino_dir, exist_ok=True)

    nombre = f"{uuid.uuid4().hex}.{extension}"
    ruta   = os.path.join(destino_dir, nombre)
    with open(ruta, "wb") as f:
        f.write(contenido)

    return f"/archivos/{carpeta}/{gym_id}/{nombre}"


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
    ruta = os.path.join(DIR_STATIC, carpeta, gym_id, nombre)
    try:
        os.remove(ruta)
    except FileNotFoundError:
        pass
