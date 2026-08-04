# CrossFit SaaS — Arquitectura, Seguridad y Deployment

---

## 1. Modelo Multi-Tenant

### Estrategia: Row-Level Tenancy
Todas las tablas de datos tienen una columna `gym_id` (UUID). Cada query
filtra por `gym_id` extraído del JWT del usuario autenticado. El `gym_id`
nunca viene del body del request — solo del token.

```
Request → JWT middleware → extrae gym_id del token → query filtra por gym_id
```

### Por qué UUID para gimnasios y usuarios
Los IDs enteros son enumerables: si un atacante sabe que existe el gym 5,
puede probar el gym 4 y el gym 6. Los UUIDs eliminan esa superficie de ataque
en las entidades críticas (gimnasios, usuarios). Las entidades internas
(miembros, ventas, productos) usan SERIAL porque el gym_id ya provee aislamiento.

---

## 2. Modelo de Seguridad

### 2.1 Autenticación: JWT (access + refresh)

```
POST /auth/login
  Body: { email, password, gym_slug }
  Response: { access_token, refresh_token }

POST /auth/refresh
  Body: { refresh_token }
  Response: { access_token }

POST /auth/logout
  Body: { refresh_token }
  Acción: elimina el refresh_token de la DB
```

**Access token**
- Algoritmo: HS256
- Payload: `{ user_id, gym_id, rol, exp }`
- Vida útil: 8 horas
- NO se guarda en DB — stateless

**Refresh token**
- Generado con `secrets.token_urlsafe(64)`
- Se guarda en DB como `SHA-256(token)` — nunca el token en claro
- Vida útil: 30 días
- Al usarse, se rota (se elimina el viejo, se crea uno nuevo)

### 2.2 Roles y permisos

| Acción                            | admin | staff |
|-----------------------------------|:-----:|:-----:|
| Ver y gestionar miembros          |  ✓    |  ✓    |
| Registrar check-in                |  ✓    |  ✓    |
| Crear/renovar membresías          |  ✓    |  ✓    |
| Operar el POS                     |  ✓    |  ✓    |
| Ver inventario                    |  ✓    |  ✓    |
| Gestionar productos/inventario    |  ✓    |  ✗    |
| Ver reportes y finanzas           |  ✓    |  ✗    |
| Gestionar gastos                  |  ✓    |  ✗    |
| Crear/eliminar usuarios           |  ✓    |  ✗    |
| Configurar el gimnasio            |  ✓    |  ✗    |

### 2.3 Middleware de autenticación (FastAPI)

```
Cada request protegido:
  1. Extrae Bearer token del header Authorization
  2. Decodifica y valida el JWT (firma + expiración)
  3. Inyecta { user_id, gym_id, rol } como dependencia
  4. La ruta usa gym_id para filtrar — nunca acepta gym_id del body
```

### 2.4 Regla de oro: gym_id solo del token
```python
# CORRECTO
@router.get("/miembros")
def listar_miembros(db, usuario_actual = Depends(get_usuario_actual)):
    return db.query(Miembro).filter(Miembro.gym_id == usuario_actual.gym_id).all()

# NUNCA HACER ESTO
@router.get("/miembros")
def listar_miembros(gym_id: str, db):   # gym_id del query param = inseguro
    return db.query(Miembro).filter(Miembro.gym_id == gym_id).all()
```

### 2.5 Onboarding de nuevo gimnasio

```
POST /auth/register-gym  (endpoint público, sin autenticación)
  Body: { gym_nombre, gym_slug, gym_email, admin_nombre, admin_email, admin_password }
  Acción:
    1. Crea fila en gimnasios
    2. Crea fila en usuarios con rol='admin'
    3. Retorna access_token + refresh_token del admin
```

---

## 3. Motor de Alertas de Membresías

El estado de cada membresía se calcula en runtime comparando `fecha_fin` con HOY.
No existe un job que actualice el campo `estado` — el campo existe para filtros
rápidos pero la lógica de alertas es computada.

```
HOY
 │
 ├─ fecha_fin < HOY                    → vencida    (gris)
 ├─ fecha_fin entre HOY y HOY + 2d     → critica    (rojo)
 ├─ fecha_fin entre HOY + 3d y HOY + 7d → por_vencer (amarillo)
 └─ fecha_fin > HOY + 7d               → activa     (verde)

Para planes por clases:
 ├─ clases_usadas >= clases_total      → vencida
 └─ clases_usadas >= clases_total - 2  → critica
```

**Endpoint de alertas:**
```
GET /membresias/alertas
  Response: {
    criticas: [{ miembro, fecha_fin, dias_restantes }],
    por_vencer: [...],
    total: N
  }
```

---

## 4. Deployment: GitHub → Google Cloud Run

### Stack de deployment

```
GitHub (repo) 
    │
    │ push a main
    ▼
GitHub Actions
    │
    ├─ Build Docker image (backend/)
    ├─ Push a Google Artifact Registry
    └─ Deploy a Cloud Run
            │
            └─ Variables de entorno desde GitHub Secrets:
               DATABASE_URL, JWT_SECRET, FRONTEND_ORIGINS
```

### Variables de entorno requeridas

| Variable          | Descripción                          | Dónde se configura       |
|-------------------|--------------------------------------|--------------------------|
| `DATABASE_URL`    | PostgreSQL URI de Supabase           | GitHub Secret + Cloud Run|
| `JWT_SECRET`      | Clave para firmar JWTs (≥32 chars)   | GitHub Secret + Cloud Run|
| `FRONTEND_ORIGINS`| URLs del/los frontend(s) en producción, separadas por coma | GitHub Secret + Cloud Run|
| `GCP_PROJECT_ID`  | ID del proyecto de Google Cloud      | GitHub Secret            |
| `GCP_SA_KEY`      | Service Account JSON para CI/CD      | GitHub Secret            |

### Ramas del repositorio

```
main   → producción (Cloud Run)
dev    → desarrollo local (no despliega)
```

Solo se despliega desde `main`. Los cambios van a `dev` y se merge a `main`
cuando están validados.

---

## 5. Estructura del Proyecto Post-Cleansing

```
POS-Crossfit/
├── CLAUDE.md
├── Dockerfile              ← build del backend para Cloud Run
├── railway.toml            ← se puede eliminar cuando Cloud Run esté configurado
├── .github/
│   └── workflows/
│       └── deploy.yml      ← CI/CD GitHub Actions
│
├── docs/
│   └── arquitectura.md     ← este documento
│
├── backend/migrations/
│   ├── 000_schema_base.sql ← schema completo, correr esta carpeta entera en orden en Supabase
│   └── 001...020_*.sql
│
├── backend/
│   ├── main.py
│   ├── database.py
│   ├── models.py           ← se reescribe con nuevas tablas
│   ├── auth.py             ← se reescribe con JWT
│   ├── security.py
│   ├── requirements.txt
│   └── routes/
│       ├── auth.py         ← nuevo: login, refresh, logout, register-gym
│       ├── miembros.py     ← renombrado desde clientes.py
│       ├── membresias.py   ← nuevo módulo core
│       ├── checkin.py      ← nuevo
│       ├── productos.py
│       ├── inventario.py
│       ├── ventas.py
│       ├── abonos.py
│       ├── dashboard.py
│       ├── finanzas.py
│       └── configuracion.py
│
└── frontend/
    └── src/
        ├── pages/
        │   ├── Dashboard.jsx
        │   ├── Miembros.jsx       ← renombrado
        │   ├── Membresias.jsx     ← nuevo
        │   ├── CheckIn.jsx        ← nuevo
        │   ├── POS.jsx
        │   ├── Inventario.jsx
        │   ├── Finanzas.jsx
        │   └── Ajustes.jsx
        └── components/
            └── Login.jsx          ← se adapta para gym_slug
```

---

## 6. Checklist antes de primera línea de código

- [ ] Supabase: proyecto creado con nuevo correo
- [ ] Supabase: backend/migrations/*.sql corridas en orden (000 a la última) en SQL Editor
- [ ] GCP: proyecto creado, Cloud Run API habilitada
- [ ] GCP: Service Account creado con rol "Cloud Run Admin" + "Artifact Registry Writer"
- [ ] GitHub: repo creado, secrets configurados
- [ ] `.env` local del backend actualizado con el DATABASE_URL de Supabase
- [ ] `main.py` limpiado (remover imports eliminados: capital, tienda, pre_pedidos, sync, ES_LOCAL)
