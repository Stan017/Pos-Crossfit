"""
Utilidades de seguridad reutilizables para toda la app.
"""
import re


# ── Sanitización de texto ──────────────────────────────────────────────────────

_TAG_RE   = re.compile(r'<[^>]+>')          # etiquetas HTML
_NULL_RE  = re.compile(r'\x00')             # bytes nulos (SQL trick)
_SCRIPT   = re.compile(r'(javascript|vbscript|data):', re.I)  # URIs peligrosas


def sanitizar(valor: str | None) -> str | None:
    """
    Limpia un string de entrada:
      - Elimina etiquetas HTML  (<script>, <img>, etc.)
      - Elimina bytes nulos
      - Elimina URIs javascript:/vbscript:/data:
      - Strip de espacios al inicio/fin
    SQLAlchemy ya usa queries parametrizadas → el ORM previene SQL Injection.
    Esta capa protege contra XSS almacenado en campos de texto.
    """
    if valor is None:
        return None
    v = _TAG_RE.sub('', valor)
    v = _NULL_RE.sub('', v)
    v = _SCRIPT.sub('', v)
    return v.strip() or None
