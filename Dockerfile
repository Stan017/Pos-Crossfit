FROM python:3.11-slim

WORKDIR /app

# Dependencias del sistema para pycairo/xhtml2pdf
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libcairo2-dev \
    pkg-config \
    && rm -rf /var/lib/apt/lists/*

# Instalar dependencias Python
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copiar codigo del backend
COPY backend/ .

# --proxy-headers + --forwarded-allow-ips='*': detrás de un proxy (Cloud Run,
# Render, Railway — todos), request.client.host es la IP del proxy, no la del
# cliente real. Sin esto, el rate limiting (limiter.py) y el bloqueo de
# intentos fallidos (platform_admin.py) tratan a TODO el tráfico como una
# sola IP. '*' porque la IP del proxy de cada plataforma no es fija/conocida
# de antemano.
CMD ["sh", "-c", "uvicorn main:app --host 0.0.0.0 --port ${PORT:-8000} --proxy-headers --forwarded-allow-ips='*'"]
