# CrossFit / Rehab SaaS

![CI](https://github.com/Stan017/Pos-Crossfit/actions/workflows/ci.yml/badge.svg)

SaaS multi-tenant para gestión de boxes de CrossFit y centros de rehabilitación
traumatológica — planes/membresías, check-in, POS, inventario, agenda de clases/
citas y facturación, con aislamiento total de datos entre gimnasios (tenants).

Migrado desde **PosRose** (POS local de ropa deportiva, Ecuador). Se reutiliza
la infraestructura FastAPI + PostgreSQL + React; el sync SQLite↔Supabase, el
modo local y los módulos no aplicables (tienda física, capital) se descartaron.

---

## Índice

- [Stack](#stack)
- [Estructura del repo](#estructura-del-repo)
- [Requisitos](#requisitos)
- [Levantar el proyecto en local](#levantar-el-proyecto-en-local)
- [Variables de entorno](#variables-de-entorno)
- [Base de datos y migraciones](#base-de-datos-y-migraciones)
- [Tests](#tests)
- [Calidad de código](#calidad-de-código)
- [CI/CD](#cicd)
- [Arquitectura](#arquitectura)
- [Licencia](#licencia)

---

## Stack

| Capa | Tecnología |
|---|---|
| Backend | FastAPI (Python 3.10) + SQLAlchemy 2.0 |
| Base de datos | PostgreSQL (Supabase en producción), con Row-Level Security real |
| Auth | JWT (cookies httpOnly) con `gym_id` en claims — tenancy enforced a nivel de token |
| Frontend | React 18 + Vite, 4 apps independientes (ver abajo) |
| PDF | xhtml2pdf (facturas, server-side) |
| Tests backend | pytest + Postgres real en Docker (nunca SQLite — RLS y JSONB/UUID no son compatibles con ese dialecto) |
| Tests frontend | Vitest + Testing Library |
| Calidad | ruff (backend), eslint (frontend) |
| CI/CD | GitHub Actions → Docker → Google Cloud Run |

## Estructura del repo

Backend y frontends son proyectos separados — el backend expone JSON, cada
frontend lo consume. Sin acoplamiento de renderizado.

```
backend/                 FastAPI. Un módulo de ruta = una entidad de negocio.
  routes/                 Endpoints — validan input, llaman al service, responden.
  services/                Lógica de negocio y orquestación (sin queries directas).
  migrations/               SQL numerado a mano (000...037), nunca destructivo.
  tests/                     pytest contra Postgres real en Docker (168 tests).

frontend/                App para gimnasios de CrossFit.
frontend-rehab/           Fork independiente para centros de rehabilitación
                           (mismo backend, mismo gym_id — terminología distinta:
                           Miembro→Paciente, Clase→Cita, Instructor→Terapeuta).
frontend-admin/           Panel del superadmin de la plataforma (multi-tenant,
                           analíticas cross-gym, gestión de suscripciones SaaS).
frontend-marketing/       Landing pública, sin lógica de negocio.
frontend-shared/          Código 100% idéntico entre frontend/ y frontend-rehab
                           (páginas de POS/Inventario/Planes/Usuarios, hooks,
                           utils), compartido vía alias de Vite — sin monorepo,
                           sin paquete npm publicado. 61 tests (Vitest).

archivo-duplicados-frontend/  Copias históricas archivadas al momento de
                                deduplicar frontend/frontend-rehab — no se
                                importan desde ningún lado, quedan por si acaso.

docs/                     Notas de arquitectura, seguridad y schema de referencia.
```

Cada gimnasio/centro es un **tenant** con datos aislados. `gym_id` está
presente en cada tabla de negocio y en cada query — no es opcional. Ver
[docs/arquitectura.md](docs/arquitectura.md) para el detalle completo del
modelo multi-tenant, RLS y decisiones de seguridad.

## Requisitos

- Python 3.10
- Node.js 18+ (desarrollado con Node 22)
- Docker Desktop (solo para correr el test suite del backend en local — la app
  en sí no necesita Docker para correr, se conecta directo a Postgres)
- Una base PostgreSQL (Supabase recomendado — el proyecto no funciona con
  SQLite: usa JSONB, `UUID(as_uuid=True)` y Row-Level Security reales)

## Levantar el proyecto en local

### Backend

```bash
cd backend
pip install -r requirements.txt
copy .env.example .env    # completar DATABASE_URL, JWT_SECRET, etc. (ver abajo)
uvicorn main:app --reload
```

Corre en `http://localhost:8000`. Con `DEBUG=true` en `.env`, Swagger queda
disponible en `/docs` (`/redoc` y `/openapi.json` también) — deshabilitado por
default, y siempre debe quedar en `false` en producción.

### Frontends

Cada app se instala y corre por separado:

```bash
cd frontend && npm install && npm run dev          # :5173 — CrossFit
cd frontend-rehab && npm install && npm run dev    # :5174 — Rehab/Médico
cd frontend-marketing && npm install && npm run dev # :5175 — Landing
cd frontend-admin && npm install && npm run dev    # :5176 — Panel superadmin
```

En desarrollo, cada app proxea `/api` a `http://localhost:8000` vía Vite — no
hace falta configurar `VITE_API_URL` en local.

**Atajo:** `backend/start.bat` arranca las 5 ventanas (backend + 4 frontends)
de una sola vez.

## Variables de entorno

Cada proyecto tiene su propio `.env.example` documentado. Las claves del
backend (`backend/.env.example`):

| Variable | Qué es |
|---|---|
| `DATABASE_URL` | Connection string de Postgres (rol `app_backend`, sin bypass de RLS) |
| `JWT_SECRET` | Generar con `python -c "import secrets; print(secrets.token_urlsafe(48))"` |
| `PLATFORM_ADMIN_KEY` | Clave del panel superadmin (`frontend-admin`) — mismo criterio de generación |
| `FRONTEND_ORIGINS` | Lista separada por coma de orígenes permitidos en CORS (un valor por cada frontend desplegado) |

`backend/.env` **nunca** se commitea (está en `.gitignore`). `.env.example`
sí, como plantilla.

## Base de datos y migraciones

Sin ORM `create_all` ni Alembic — el schema vive enteramente en
`backend/migrations/*.sql`, numeradas a mano y aplicadas en orden. Toda
migración nueva es **aditiva** (nunca `DROP`/recrea con datos de tenants
vivos) y termina con su propio `INSERT INTO schema_migrations (...)`.

```bash
cd backend
python check_migrations.py   # diagnóstico read-only: compara migrations/ vs. lo ya aplicado
```

## Tests

### Backend — 168 tests, Postgres real (no mocks, no SQLite)

```bash
docker compose -f backend/tests/docker-compose.test.yml up -d --wait
cd backend
pytest
```

Corre contra un Postgres efímero en Docker con los mismos roles de producción
(`app_backend` sin bypass de RLS, `app_platform` con bypass para el panel
superadmin) — así los tests de aislamiento multi-tenant prueban el mecanismo
real, no una versión debilitada. El container no se baja solo entre corridas
(evita re-aplicar las migraciones cada vez); `docker compose ... down` para
un schema realmente limpio.

### Frontend — 61 tests (Vitest + Testing Library), en `frontend-shared/`

```bash
cd frontend-shared
npm test              # correr una vez
npm run test:coverage # con reporte de cobertura
```

Es la única carpeta del repo con tests de frontend hoy — cubre las funciones
puras, hooks y componentes de POS que comparten `frontend/` y `frontend-rehab/`.

## Calidad de código

```bash
# Backend
cd backend && ruff check .

# Frontend (por cada app: frontend/, frontend-rehab/, frontend-admin/, frontend-shared/)
npm run lint
```

Ambas herramientas corren en cada push/PR como parte del gate de CI (ver
abajo). Sin gate de coverage todavía — se mide como diagnóstico, no bloquea.

## CI/CD

[`.github/workflows/ci.yml`](.github/workflows/ci.yml) corre en cada `push` a
`master` y en cada Pull Request:

1. **`backend-tests`** — `ruff check` + `pytest` (Postgres real vía Docker,
   igual que en local).
2. **`frontend-lint`** — `eslint` en las 4 apps React (job en paralelo, matrix).
3. **`frontend-shared-tests`** — `vitest run`.
4. **`deploy`** — build de la imagen Docker del backend + push a Artifact
   Registry + deploy a Cloud Run. Solo corre en `push` a `master`, y solo si
   los tres jobs anteriores pasaron (`needs: [...]`) — un commit que rompe
   tests o lint nunca llega a producción.

El job de deploy necesita 5 secrets configurados en el repo de GitHub
(`GCP_SA_KEY`, `GCP_PROJECT_ID`, `DATABASE_URL`, `JWT_SECRET`,
`FRONTEND_ORIGINS`) — todavía no están cargados, así que ese job queda en
rojo hasta que se configure el deploy real a Cloud Run.

## Arquitectura

Documentación extendida de modelo multi-tenant, RLS, decisiones de seguridad
e infraestructura en [`docs/arquitectura.md`](docs/arquitectura.md) y
[`docs/infraestructura.txt`](docs/infraestructura.txt).

## Licencia

MIT — ver [LICENSE](LICENSE).
