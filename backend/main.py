import contextvars
import logging
import uuid
from contextlib import asynccontextmanager
from logging.handlers import RotatingFileHandler
from pathlib import Path
from fastapi import Depends, FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from limiter import limiter
from database import DEBUG
import os

# request_id: generado por RequestIDMiddleware (más abajo) al inicio de cada
# request, vía contextvar en vez de pasarlo a mano por cada función — así
# cualquier logger.info/error/exception de cualquier módulo lo incluye
# automáticamente sin que cada llamada tenga que conocerlo.
request_id_var = contextvars.ContextVar("request_id", default="-")


class RequestIDLogFilter(logging.Filter):
    def filter(self, record):
        record.request_id = request_id_var.get()
        return True


LOG_FORMAT = "%(asctime)s %(levelname)s [%(request_id)s] %(name)s: %(message)s"

logging.basicConfig(level=logging.INFO, format=LOG_FORMAT)

# Persistido a archivo además de stdout — stdout solo no alcanza para
# revisar un error después del hecho si nadie estaba mirando la consola en
# el momento (ver [[project_frontend_shared]] / gap review: "sin error
# tracking"). Rotación para no crecer sin límite.
LOG_DIR = Path(__file__).resolve().parent / "logs"
LOG_DIR.mkdir(exist_ok=True)
_file_handler = RotatingFileHandler(LOG_DIR / "backend.log", maxBytes=5 * 1024 * 1024, backupCount=5, encoding="utf-8")
_file_handler.setFormatter(logging.Formatter(LOG_FORMAT))

_id_filter = RequestIDLogFilter()
_file_handler.addFilter(_id_filter)
for _handler in logging.getLogger().handlers:
    _handler.addFilter(_id_filter)
logging.getLogger().addHandler(_file_handler)

logger = logging.getLogger("crossfit_saas")

# El límite grande (8MB) es solo para lo que sube un archivo: una foto de
# comprobante desde un celular sin comprimir ronda 2-6MB. Todo lo demás —
# login, crear un miembro, registrar una venta — es JSON de un par de KB, y
# no hay ninguna razón para dejarlo aceptar 8MB de body antes de rechazarlo.
# El discriminador es el Content-Type, no la ruta: cualquier endpoint que
# reciba un archivo ya declara multipart/form-data, así que no hace falta
# mantener una lista de paths a mano ni desincronizarla cuando se agregue
# un endpoint de upload nuevo.
MAX_BODY_BYTES_JSON      = 2 * 1024 * 1024  # 2 MB — límite original, pensado para JSON
MAX_BODY_BYTES_MULTIPART = 8 * 1024 * 1024  # 8 MB — comprobantes y fotos de producto


class _BodyDemasiadoGrande(Exception):
    pass


class LimitBodyMiddleware:
    """
    ASGI puro, no BaseHTTPMiddleware: envolver/reemplazar el receive() de un
    Request dentro de un middleware dispatch() rompe el protocolo ASGI que
    espera cualquier BaseHTTPMiddleware que lo envuelva por fuera (acá,
    SecurityHeadersMiddleware) — "RuntimeError: Unexpected message received".
    Esto cuenta bytes a medida que la app los va pidiendo, sin bufferear ni
    reemplazar nada.
    """
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        content_length = None
        content_type   = b""
        for nombre, valor in scope.get("headers", []):
            if nombre == b"content-length":
                content_length = valor
            elif nombre == b"content-type":
                content_type = valor
        limite = (
            MAX_BODY_BYTES_MULTIPART
            if content_type.startswith(b"multipart/form-data")
            else MAX_BODY_BYTES_JSON
        )

        if content_length and int(content_length) > limite:
            response = JSONResponse(status_code=413, content={"detail": "Payload demasiado grande."})
            await response(scope, receive, send)
            return

        total = 0

        async def receive_limitado():
            nonlocal total
            mensaje = await receive()
            if mensaje["type"] == "http.request":
                total += len(mensaje.get("body", b""))
                if total > limite:
                    raise _BodyDemasiadoGrande()
            return mensaje

        try:
            await self.app(scope, receive_limitado, send)
        except _BodyDemasiadoGrande:
            response = JSONResponse(status_code=413, content={"detail": "Payload demasiado grande."})
            await response(scope, receive, send)


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        response.headers["X-Content-Type-Options"]  = "nosniff"
        response.headers["X-Frame-Options"]         = "DENY"
        response.headers["X-XSS-Protection"]        = "1; mode=block"
        response.headers["Referrer-Policy"]         = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"]      = "geolocation=(), camera=(), microphone=()"
        response.headers["Strict-Transport-Security"] = "max-age=63072000; includeSubDomains"
        return response


class RequestIDMiddleware(BaseHTTPMiddleware):
    """
    Se registra último (ver más abajo) para quedar como el middleware más
    externo — necesita correr antes que cualquier otro para que el
    contextvar esté seteado cuando algo downstream loguea, incluida la
    propia respuesta 413 de LimitBodyMiddleware.
    """
    async def dispatch(self, request: Request, call_next):
        req_id = str(uuid.uuid4())
        token = request_id_var.set(req_id)
        try:
            request.state.request_id = req_id
            response = await call_next(request)
            response.headers["X-Request-ID"] = req_id
            return response
        finally:
            request_id_var.reset(token)

import models  # noqa: F401 — registra todos los modelos en SQLAlchemy
import audit   # noqa: F401 — registra el listener de audit log

from routes import (
    auth, miembros, membresias, checkin, planes, usuarios,
    productos, inventario, ventas, abonos, deudas,
    dashboard, finanzas, configuracion, imagenes, facturas,
    suscripciones, horarios, archivos, instructores, historial_medico,
    admin_analytics, errores_frontend,
)
from auth import require_gym_activa

@asynccontextmanager
async def lifespan(app: FastAPI):
    yield

app = FastAPI(
    title="CrossFit SaaS API",
    description="Backend multi-tenant para gestión de boxes de CrossFit",
    version="1.0.0",
    lifespan=lifespan,
    # DEBUG=true en .env habilita /docs, /redoc y el schema OpenAPI —
    # deshabilitados por default (nunca en producción).
    docs_url=    "/docs"        if DEBUG else None,
    redoc_url=   "/redoc"       if DEBUG else None,
    openapi_url= "/openapi.json" if DEBUG else None,
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.add_middleware(LimitBodyMiddleware)
app.add_middleware(SecurityHeadersMiddleware)

@app.exception_handler(Exception)
async def error_generico(request: Request, exc: Exception):
    logger.exception("Error no manejado en %s %s", request.method, request.url.path)
    return JSONResponse(
        status_code=500,
        content={"detail": "Error interno del servidor."},
    )

# Lista separada por coma: un backend compartido sirve a varios frontends
# (CrossFit, el fork médico/rehab, y el panel de plataforma), cada uno con
# su propio origen. Default cubre los puertos que Vite usa en dev cuando
# todos corren en paralelo local (5173 -> 5174 -> 5175 -> 5176 si el
# anterior está ocupado).
FRONTEND_ORIGINS = [
    o.strip() for o in
    os.getenv(
        "FRONTEND_ORIGINS",
        "http://localhost:5173,http://localhost:5174,http://localhost:5176",
    ).split(",")
    if o.strip()
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=FRONTEND_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Último = más externo (Starlette envuelve en orden inverso de agregado) —
# tiene que correr antes que todo lo demás para que el request_id exista
# cuando cualquier middleware/ruta downstream loguee.
app.add_middleware(RequestIDMiddleware)

# ── Rutas públicas ────────────────────────────────────────────────────────────
app.include_router(auth.router,         prefix="/auth",         tags=["Auth"])

# Sin auth ni require_gym_activa a propósito: un crash de React puede pasar
# en la pantalla de Login, antes de que exista cualquier sesión.
app.include_router(errores_frontend.router, prefix="/errores-frontend", tags=["Errores frontend"])

# Archivos subidos (comprobantes, fotos de producto): requieren estar logueado
# (Depends(get_usuario_actual) adentro de la ruta), pero no exigen suscripción
# activa — un gym con la suscripción vencida igual tiene que poder ver sus
# comprobantes de pago viejos. Por eso no lleva dependencies=_gym_activa.
app.include_router(archivos.router,     prefix="/archivos",     tags=["Archivos"])

# ── Suscripciones (sin require_gym_activa: gyms vencidos deben poder ver su estado) ──
app.include_router(suscripciones.gym_router,   prefix="/suscripciones",        tags=["Suscripciones"])
app.include_router(suscripciones.admin_router, prefix="/admin/suscripciones",  tags=["SaaS Admin"])
app.include_router(admin_analytics.router,     prefix="/admin/analytics",      tags=["SaaS Admin"])

# ── Rutas de negocio (requieren JWT válido + suscripción activa) ──────────────
_gym_activa = [Depends(require_gym_activa)]

app.include_router(miembros.router,     prefix="/miembros",     tags=["Miembros"],       dependencies=_gym_activa)
app.include_router(membresias.router,   prefix="/membresias",   tags=["Membresías"],     dependencies=_gym_activa)
app.include_router(planes.router,       prefix="/planes",       tags=["Planes"],         dependencies=_gym_activa)
app.include_router(usuarios.router,     prefix="/usuarios",     tags=["Usuarios"],       dependencies=_gym_activa)
app.include_router(checkin.router,      prefix="/checkin",      tags=["Check-in"],       dependencies=_gym_activa)
app.include_router(productos.router,    prefix="/productos",    tags=["Productos"],      dependencies=_gym_activa)
app.include_router(inventario.router,   prefix="/inventario",   tags=["Inventario"],     dependencies=_gym_activa)
app.include_router(ventas.router,       prefix="/ventas",       tags=["Ventas"],         dependencies=_gym_activa)
app.include_router(abonos.router,       prefix="/abonos",       tags=["Abonos"],         dependencies=_gym_activa)
app.include_router(deudas.router,       prefix="/deudas",       tags=["Deudas"],         dependencies=_gym_activa)
app.include_router(dashboard.router,    prefix="/dashboard",    tags=["Dashboard"],      dependencies=_gym_activa)
app.include_router(finanzas.router,     prefix="/finanzas",     tags=["Finanzas"],       dependencies=_gym_activa)
app.include_router(configuracion.router,prefix="/configuracion",tags=["Configuración"],  dependencies=_gym_activa)
app.include_router(imagenes.router,     prefix="/productos",    tags=["Imágenes"],       dependencies=_gym_activa)
app.include_router(facturas.router,     prefix="/facturas",     tags=["Facturas"],       dependencies=_gym_activa)
app.include_router(horarios.router,     prefix="/horarios",     tags=["Horarios"],       dependencies=_gym_activa)
app.include_router(instructores.router, prefix="/instructores", tags=["Instructores"],   dependencies=_gym_activa)
app.include_router(historial_medico.router, prefix="/historial-medico", tags=["Historial médico"], dependencies=_gym_activa)


@app.get("/health")
def health():
    return {"status": "ok", "app": "CrossFit SaaS"}

@app.get("/")
def root():
    return {"status": "ok", "app": "CrossFit SaaS"}
