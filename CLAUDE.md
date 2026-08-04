# CLAUDE.md

## Core Philosophy

No change gets made without first being understood completely. Every line of code exists for a reason. Before touching anything: read it, trace it, question it.

If the analysis isn't done, the change isn't made. Period.

The architecture is the most expensive decision to change. It gets validated before a single line of implementation is written.

---

## Project: CrossFit SaaS (working name)

SaaS multi-tenant para gestión de boxes de CrossFit, inspirado en CrossHero.
Múltiples gimnasios como tenants independientes. Acceso vía web, sin instalación local.

Base de código: migrado desde PosRose (POS local ropa deportiva Ecuador).
La infraestructura FastAPI + PostgreSQL + React de PosRose se reutiliza.
El sync SQLite↔Supabase, modo local, y módulos no aplicables (tienda, capital) se descartan.

### Stack

| Capa | Tecnología | Razón |
|---|---|---|
| Backend | FastAPI (Python) | Async nativo, validación Pydantic, PostgreSQL nativo |
| Base de datos | PostgreSQL (Supabase) | Multi-tenant, un solo servidor cloud |
| Auth | JWT con gym_id en claims | Tenancy enforced a nivel de token |
| Frontend | React + Vite | Estático en producción, sin node_modules en servidor |
| Charts | Recharts | Ya integrado, sin overhead adicional |
| PDF | xhtml2pdf (Python) | Server-side, sin dependencia del browser |

**Backend y frontend son proyectos separados.** El backend expone JSON. El frontend consume JSON. No hay acoplamiento de renderizado.

### Módulos objetivo

1. **Auth** — login por email/password, JWT, roles (admin / staff)
2. **Miembros** — CRUD, historial de membresías, estado activo/inactivo
3. **Membresías** — planes por tiempo (mensual/trimestral/anual) y por clases (pack 10/20)
4. **Alertas** — motor: 3-7 días → amarillo, 0-2 días → rojo, vencida → gris
5. **POS** — venta rápida de productos (suplementos, merch), carrito, cobro
6. **Inventario** — CRUD productos, stock, alertas de stock mínimo
7. **Check-in** — registro de asistencia, descuento de clase si aplica
8. **Dashboard** — KPIs: membresías activas, alertas, revenue del mes, asistencia
9. **Reportes** — ingresos por período, membresías por estado, productos más vendidos

### Contexto de negocio

- Multi-tenant: cada box de CrossFit es un tenant con sus propios datos aislados
- gym_id está presente en cada tabla y cada query — no es opcional
- Dos tipos de plan de membresía: por duración (fecha fin) y por clases (contador)
- Un miembro puede tener solo una membresía activa a la vez
- Las ventas del POS son independientes de las membresías (productos físicos)
- Un pago de membresía puede registrarse desde el POS como ítem especial

---

## Engineering Standards

- **Read before writing.** Always read the full context of a file or function before modifying it.
- **Understand the why.** If the reason a piece of code exists isn't clear, find out before changing it.
- **No speculative changes.** Don't "clean up" or "improve" things that aren't broken and aren't part of the task.
- **No half-measures.** A fix that solves 80% of the problem is not a fix — it's a future bug.
- **Simple over clever.** The best code is the code that doesn't need a comment to explain it.
- **One concern per change.** Don't bundle unrelated fixes. Small, focused, reviewable.

---

## Analysis Before Action

Before any implementation:

1. Identify exactly what needs to change and why.
2. Name the exact caller(s) of every function you're about to write.
3. Trace all dependencies and side effects.
4. Confirm the change doesn't break adjacent behavior.
5. Only then: write the code.

If something unexpected is discovered mid-implementation, stop. Re-analyze. Don't bulldoze through.

---

## Architecture Rules

### Schema First
The data model is the contract. No endpoint gets written before the schema for that module is decided and documented. If the schema is wrong, every layer above it is wrong.

Order of work for any new module:
1. Define tables and columns (with types, constraints, nullability)
2. Define API response shape (what fields, what types, what's nullable)
3. Write the service logic
4. Write the route
5. Write the frontend

### Multi-Tenancy is Non-Negotiable
`gym_id` is present in every table that holds business data. Every query that reads or writes business data must filter by `gym_id` from the JWT claims. An endpoint that returns data without tenant isolation is a security bug, not a missing feature. This is verified before any route is considered complete.

### Layer Discipline
Each layer has one job. Mixing them creates unmaintainable 400-line functions.

| Layer | Responsibility | What it must NOT do |
|---|---|---|
| Route | Validate input, call service, return response | Contain business logic or DB queries |
| Service | Business logic, orchestration | Direct DB access — use repository functions |
| Model/Repository | DB queries only | Contain business decisions |

### Dead Code Protocol
Before writing a function, name exactly which code will call it. If you can't name the caller, don't write the function. A utility with no caller is dead code before it's committed. There are no "helper functions for later."

### Explicit Side Effects
If a function has a side effect beyond returning a value — decrements stock, sends a notification, updates a membership status, creates a log entry — that side effect must be explicit in the function name or clearly documented in its signature. Hidden side effects are the primary source of logic bugs.

Wrong: `crear_venta(db, datos)` — silently decrements stock and marks membership
Right: `crear_venta_y_descontar_stock(db, datos)` — or split into two explicit calls

### Nullability is Intentional
Before making any field nullable, answer:
- What does the frontend render when this field is null?
- What does the API do when this field is null?
- Is null a valid business state or just "I'll handle it later"?

Nullable by default is a bug disguised as flexibility. Every nullable field must have a documented reason.

### No Boolean Parameters
A function that changes behavior based on a boolean flag is two functions pretending to be one.

Wrong: `procesar_pago(db, datos, es_membresia=True)`
Right: `registrar_pago_membresia(db, datos)` and `registrar_pago_producto(db, datos)`

### Migrations Over Drops
In a SaaS with live tenant data, you never drop and recreate. Every schema change is an additive migration. A migration that destroys existing data requires explicit written justification before it runs.

### Unhappy Path First
Before writing the happy path, define:
- What happens when stock is 0?
- What happens when the membership is expired?
- What happens when the payment method is missing?
- What is the HTTP status code and error message for each case?

These are not edge cases. They are expected states the system must handle explicitly.

### Diagram Before Code (3+ Tables)
Any new module or feature that touches three or more tables requires a data flow diagram before implementation starts. The diagram shows: which tables are read, which are written, in what order, and under what conditions. This is drawn and reviewed before any `.py` file is opened.

---

## What Gets Rejected

- Cosmetic refactors bundled with functional changes.
- Abstractions introduced "for the future."
- Code that adds complexity without adding value.
- Changes that haven't been traced through their full impact.
- Anything done "just to try it."
- Functions without a named caller.
- Boolean parameters that change function behavior.
- Nullable fields without documented reason.
- Routes that don't filter by gym_id when handling business data.
- Schema changes without a migration strategy.

---

## Output Location

All files — new modules, schemas, scripts, plans, diagrams — are written directly inside `C:\Users\stanley\Desktop\POS-Crossfit`. Never in `/tmp`, scratchpad, or any temporary location. If it's part of the work, it lives in the project.

---

## Communication Style

Be direct. If something is wrong, say it's wrong. If a design decision is bad, explain why with precision — not vague discomfort. Opinions must be backed by reasoning, not preference.

No sugarcoating. No padding. Say what needs to be said and move on.

When proposing a new module or significant change: present the schema and API shape first. Do not present code. Code comes after the design is validated.

---

## On Bugs

A bug report without a reproducible case is noise. A fix without understanding the root cause is a future regression. Bugs get fixed at the source, not patched at the symptom.

---

## On Dependencies

Every external dependency is a liability. Before adding one: verify it's necessary, verify its quality, and accept that you now own understanding it. In this project the existing stack (FastAPI, SQLAlchemy, React, Recharts, xhtml2pdf) covers the vast majority of needs. A new dependency requires a written reason for why the existing stack cannot solve the problem.
