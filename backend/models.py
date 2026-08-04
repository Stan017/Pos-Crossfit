from sqlalchemy import (
    Column, Integer, BigInteger, String, Float, Numeric, Boolean,
    DateTime, Date, Time, ForeignKey, Text, Enum, UniqueConstraint, Index,
    CheckConstraint
)
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from database import Base
import enum
import uuid


# ─────────────────────────────────────────
# Enums
# ─────────────────────────────────────────

class RolUsuario(str, enum.Enum):
    admin = "admin"
    staff = "staff"

class TipoPlan(str, enum.Enum):
    tiempo = "tiempo"
    clases = "clases"

class EstadoMembresia(str, enum.Enum):
    activa          = "activa"
    por_vencer      = "por_vencer"
    critica         = "critica"
    pendiente_pago  = "pendiente_pago"
    vencida         = "vencida"
    cancelada       = "cancelada"

class MetodoPago(str, enum.Enum):
    efectivo      = "efectivo"
    transferencia = "transferencia"
    tarjeta       = "tarjeta"

class EstadoVenta(str, enum.Enum):
    pagada    = "pagada"
    abono     = "abono"
    cancelada = "cancelada"

class SaasPlan(str, enum.Enum):
    trial      = "trial"
    mensual    = "mensual"
    trimestral = "trimestral"
    semestral  = "semestral"
    anual      = "anual"

class SaasEstado(str, enum.Enum):
    trial      = "trial"
    activa     = "activa"
    por_vencer = "por_vencer"
    # Vencida hace poco, pero todavía dentro de la ventana de 4 días hábiles
    # de prórroga (ver services/suscripciones_service.py) — tiene acceso
    # igual que 'activa', pero se muestra distinto para que el gym y el
    # platform admin vean que está corriendo el plazo, no que está al día.
    en_gracia  = "en_gracia"
    vencida    = "vencida"
    suspendida = "suspendida"

# Capacidad de staff (cuántos médicos/coaches y asistentes admite el
# gimnasio), independiente de saas_plan (ciclo de facturación) y saas_estado
# (ciclo de vida de la suscripción). Ver TIER_LIMITES en
# services/planes_service.py para los topes de cada uno.
class SaasTier(str, enum.Enum):
    trial         = "trial"
    # $20/mes, mismos límites que trial (1 médico/coach + 1 asistente) pero
    # de pago — para operadores solo, sin necesidad de crecer más allá de lo
    # que trial ya ofrecía. Autoservicio: el gym lo puede pedir directo (ver
    # routes/suscripciones.py), a diferencia de estandar/clinica/personalizado.
    solo          = "solo"
    estandar      = "estandar"
    clinica       = "clinica"
    personalizado = "personalizado"

class EstadoPagoSaas(str, enum.Enum):
    pendiente  = "pendiente"
    confirmado = "confirmado"
    rechazado  = "rechazado"

class EstadoClase(str, enum.Enum):
    programada = "programada"
    en_curso   = "en_curso"
    completada = "completada"
    cancelada  = "cancelada"

class EstadoReservacion(str, enum.Enum):
    confirmada = "confirmada"
    cancelada  = "cancelada"
    no_show    = "no_show"

class TipoHistorialMedico(str, enum.Enum):
    patologia        = "patologia"
    lesion_previa     = "lesion_previa"
    operacion_previa  = "operacion_previa"

class VerticalNegocio(str, enum.Enum):
    crossfit = "crossfit"
    medico   = "medico"

class TipoInstructor(str, enum.Enum):
    entrenador = "entrenador"
    doctor     = "doctor"
    asistente  = "asistente"


# ─────────────────────────────────────────
# GIMNASIOS (raíz del multi-tenant)
# ─────────────────────────────────────────

class Gimnasio(Base):
    __tablename__ = "gimnasios"

    id          = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    nombre      = Column(String(200), nullable=False)
    slug        = Column(String(100), nullable=False, unique=True)
    email       = Column(String(150), nullable=False, unique=True)
    telefono    = Column(String(20))
    ruc         = Column(String(20))
    direccion   = Column(Text)
    pais        = Column(String(100), default="Ecuador")
    logo_url    = Column(String(300))
    iva_default      = Column(Float, default=0.0)
    activo           = Column(Boolean, default=True)
    creado_en        = Column(DateTime(timezone=True), server_default=func.now())
    saas_plan        = Column(Enum(SaasPlan),   nullable=False, default=SaasPlan.trial)
    saas_estado      = Column(Enum(SaasEstado), nullable=False, default=SaasEstado.trial)
    saas_tier        = Column(Enum(SaasTier),   nullable=False, default=SaasTier.trial)
    saas_vence_en    = Column(Date)   # NULL durante trial
    saas_trial_hasta = Column(Date)   # seteado al registrar
    # Qué frontend le corresponde a este gimnasio (crossfit/ vs frontend-rehab/).
    # NOT NULL: todo gimnasio es de un vertical desde que se crea, nunca "sin
    # decidir" — lo valida /auth/login contra la constante que manda cada
    # frontend, para que un login con credenciales correctas pero en el
    # frontend equivocado no entre mostrando las etiquetas de otro negocio.
    vertical         = Column(Enum(VerticalNegocio), nullable=False)

    usuarios    = relationship("Usuario",    back_populates="gimnasio", cascade="all, delete-orphan")
    miembros    = relationship("Miembro",    back_populates="gimnasio", cascade="all, delete-orphan")
    planes      = relationship("Plan",       back_populates="gimnasio", cascade="all, delete-orphan")
    productos   = relationship("Producto",   back_populates="gimnasio", cascade="all, delete-orphan")
    ventas      = relationship("Venta",      back_populates="gimnasio", cascade="all, delete-orphan")
    gastos      = relationship("Gasto",      back_populates="gimnasio", cascade="all, delete-orphan")
    # Sin delete-orphan a propósito: pagos_saas es el historial de
    # facturación de la PLATAFORMA (no datos del tenant que deban
    # desaparecer con él) — ver ondelete="RESTRICT" en PagoSaas.gym_id más
    # abajo, que es lo que realmente impide borrarlos en cascada.
    pagos_saas  = relationship("PagoSaas",   back_populates="gimnasio")


# ─────────────────────────────────────────
# USUARIOS (staff / admin por gimnasio)
# ─────────────────────────────────────────

class Usuario(Base):
    __tablename__ = "usuarios"
    __table_args__ = (
        UniqueConstraint("gym_id", "email", name="uq_usuario_gym_email"),
    )

    id            = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    gym_id        = Column(UUID(as_uuid=True), ForeignKey("gimnasios.id", ondelete="CASCADE"), nullable=False)
    email         = Column(String(150), nullable=False)
    password_hash = Column(String(255), nullable=False)
    nombre        = Column(String(200), nullable=False)
    # Nullable: los usuarios creados antes de este campo no tienen este dato
    # y no se les va a inventar uno. Se exige obligatorio a nivel de
    # formulario solo para registros nuevos (ver RegisterGymInput).
    apellido          = Column(String(200))
    fecha_nacimiento  = Column(Date)
    rol           = Column(Enum(RolUsuario), nullable=False, default=RolUsuario.staff)
    activo        = Column(Boolean, default=True)
    creado_en     = Column(DateTime(timezone=True), server_default=func.now())

    gimnasio        = relationship("Gimnasio", back_populates="usuarios")
    refresh_tokens  = relationship("RefreshToken", back_populates="usuario", cascade="all, delete-orphan")


# ─────────────────────────────────────────
# REFRESH TOKENS
# ─────────────────────────────────────────

class RefreshToken(Base):
    __tablename__ = "refresh_tokens"

    id          = Column(Integer, primary_key=True, index=True)
    usuario_id  = Column(UUID(as_uuid=True), ForeignKey("usuarios.id", ondelete="CASCADE"), nullable=False)
    # Denormalizado desde usuarios.gym_id (migración 030): rotar_refresh_token()
    # necesita saber el gym ANTES de poder consultar Usuario bajo RLS — es la
    # fila que se lee justamente para descubrir a quién pertenece el token.
    # Inmutable por fila: un usuario no cambia de gym sin una cuenta nueva.
    gym_id      = Column(UUID(as_uuid=True), ForeignKey("gimnasios.id", ondelete="CASCADE"), nullable=False)
    token_hash  = Column(String(255), nullable=False, unique=True)
    expira_en   = Column(DateTime(timezone=True), nullable=False)
    creado_en   = Column(DateTime(timezone=True), server_default=func.now())
    usado_en    = Column(DateTime(timezone=True))  # NULL = todavía no se rotó

    usuario = relationship("Usuario", back_populates="refresh_tokens")


# ─────────────────────────────────────────
# MIEMBROS
# ─────────────────────────────────────────

class Miembro(Base):
    __tablename__ = "miembros"

    id                   = Column(Integer, primary_key=True, index=True)
    gym_id               = Column(UUID(as_uuid=True), ForeignKey("gimnasios.id", ondelete="CASCADE"), nullable=False)
    nombre               = Column(String(200), nullable=False)
    apellido             = Column(String(200), nullable=False)
    email                = Column(String(150))
    telefono             = Column(String(20))
    cedula               = Column(String(20))
    fecha_ingreso        = Column(Date, nullable=False)
    fecha_nacimiento     = Column(Date)
    contacto_emergencia  = Column(String(200))
    peso                 = Column(Numeric(5, 1))  # kg — nullable, no todos lo tienen registrado
    altura               = Column(Numeric(5, 1))  # cm
    foto_url             = Column(String(300))
    notas                = Column(Text)
    activo               = Column(Boolean, default=True)
    creado_en            = Column(DateTime(timezone=True), server_default=func.now())

    gimnasio        = relationship("Gimnasio", back_populates="miembros")
    membresias      = relationship("Membresia", back_populates="miembro", cascade="all, delete-orphan")
    asistencias     = relationship("Asistencia", back_populates="miembro")
    ventas          = relationship("Venta", back_populates="miembro")
    historial_medico = relationship("HistorialMedico", back_populates="paciente", cascade="all, delete-orphan")


# ─────────────────────────────────────────
# PLANES (plantillas de membresía por gimnasio)
# ─────────────────────────────────────────

class Plan(Base):
    __tablename__ = "planes"
    __table_args__ = (
        # Ya existen como CHECK en la base de datos (migración 000) — acá
        # solo se declaran para que el ORM refleje ese invariante real, no
        # para crearlo de nuevo.
        CheckConstraint(
            "tipo != 'tiempo' OR duracion_dias IS NOT NULL",
            name="plan_tiempo_requiere_dias",
        ),
        CheckConstraint(
            "tipo != 'clases' OR clases_total IS NOT NULL",
            name="plan_clases_requiere_clases",
        ),
    )

    id             = Column(Integer, primary_key=True, index=True)
    gym_id         = Column(UUID(as_uuid=True), ForeignKey("gimnasios.id", ondelete="CASCADE"), nullable=False)
    nombre         = Column(String(200), nullable=False)
    tipo           = Column(Enum(TipoPlan), nullable=False)
    duracion_dias  = Column(Integer)   # solo tipo='tiempo'
    clases_total   = Column(Integer)   # solo tipo='clases'
    precio         = Column(Numeric(10, 2), nullable=False)
    activo         = Column(Boolean, default=True)
    creado_en      = Column(DateTime(timezone=True), server_default=func.now())

    gimnasio   = relationship("Gimnasio", back_populates="planes")
    membresias = relationship("Membresia", back_populates="plan")


# ─────────────────────────────────────────
# MEMBRESÍAS
# ─────────────────────────────────────────

class Membresia(Base):
    __tablename__ = "membresias"

    id             = Column(Integer, primary_key=True, index=True)
    gym_id         = Column(UUID(as_uuid=True), ForeignKey("gimnasios.id", ondelete="CASCADE"), nullable=False)
    miembro_id     = Column(Integer, ForeignKey("miembros.id", ondelete="CASCADE"), nullable=False)
    plan_id        = Column(Integer, ForeignKey("planes.id"), nullable=False)
    fecha_inicio   = Column(Date, nullable=False)
    fecha_fin      = Column(Date)          # NULL para planes por clases
    precio_pagado   = Column(Numeric(10, 2), nullable=False)
    precio_acordado = Column(Numeric(10, 2))  # NULL para registros previos a migración 003
    metodo_pago     = Column(Enum(MetodoPago), nullable=False)
    clases_total    = Column(Integer)      # copia del plan al momento de crear
    clases_usadas   = Column(Integer, default=0)
    estado          = Column(Enum(EstadoMembresia), nullable=False, default=EstadoMembresia.activa)
    notas           = Column(Text)
    creado_en       = Column(DateTime(timezone=True), server_default=func.now())
    creado_por      = Column(UUID(as_uuid=True), ForeignKey("usuarios.id"))

    gimnasio    = relationship("Gimnasio")
    miembro     = relationship("Miembro", back_populates="membresias")
    plan        = relationship("Plan", back_populates="membresias")
    asistencias = relationship("Asistencia", back_populates="membresia")
    pagos       = relationship("PagoMembresia", back_populates="membresia", cascade="all, delete-orphan")


# ─────────────────────────────────────────
# ASISTENCIAS (check-in)
# ─────────────────────────────────────────

class Asistencia(Base):
    __tablename__ = "asistencias"
    __table_args__ = (
        UniqueConstraint("clase_id", "miembro_id", name="uq_asistencia_clase_miembro"),
    )

    id              = Column(Integer, primary_key=True, index=True)
    gym_id          = Column(UUID(as_uuid=True), ForeignKey("gimnasios.id", ondelete="CASCADE"), nullable=False)
    miembro_id      = Column(Integer, ForeignKey("miembros.id"), nullable=False)
    membresia_id    = Column(Integer, ForeignKey("membresias.id"), nullable=False)
    clase_id        = Column(Integer, ForeignKey("clases.id", ondelete="RESTRICT"), nullable=False)
    reservacion_id  = Column(Integer, ForeignKey("reservaciones.id", ondelete="SET NULL"))
    fecha           = Column(DateTime(timezone=True), server_default=func.now())
    notas           = Column(Text)

    miembro     = relationship("Miembro", back_populates="asistencias")
    membresia   = relationship("Membresia", back_populates="asistencias")
    clase       = relationship("Clase", back_populates="asistencias")
    reservacion = relationship("Reservacion")


# ─────────────────────────────────────────
# PRODUCTOS
# ─────────────────────────────────────────

class Producto(Base):
    __tablename__ = "productos"

    id            = Column(Integer, primary_key=True, index=True)
    gym_id        = Column(UUID(as_uuid=True), ForeignKey("gimnasios.id", ondelete="CASCADE"), nullable=False)
    nombre        = Column(String(200), nullable=False)
    categoria     = Column(String(100))
    precio_venta  = Column(Numeric(10, 2), nullable=False)
    precio_costo  = Column(Numeric(10, 2), nullable=False, default=0)
    stock         = Column(Integer, default=0)
    stock_minimo  = Column(Integer, default=0)
    codigo_barra  = Column(String(100))
    imagen_url    = Column(String(300))
    activo        = Column(Boolean, default=True)
    creado_en     = Column(DateTime(timezone=True), server_default=func.now())

    gimnasio    = relationship("Gimnasio", back_populates="productos")
    venta_items = relationship("VentaItem", back_populates="producto")


# ─────────────────────────────────────────
# VENTAS (POS)
# ─────────────────────────────────────────

class Venta(Base):
    __tablename__ = "ventas"

    id             = Column(Integer, primary_key=True, index=True)
    gym_id         = Column(UUID(as_uuid=True), ForeignKey("gimnasios.id", ondelete="CASCADE"), nullable=False)
    miembro_id     = Column(Integer, ForeignKey("miembros.id"))  # nullable = venta anónima
    subtotal       = Column(Numeric(10, 2), nullable=False)
    porcentaje_iva = Column(Float, default=0.0)  # tasa (ej. 12.0 = 12%), no monto
    monto_iva      = Column(Numeric(10, 2), default=0.0)
    total          = Column(Numeric(10, 2), nullable=False)
    estado         = Column(Enum(EstadoVenta), nullable=False, default=EstadoVenta.pagada)
    notas          = Column(Text)
    creado_en      = Column(DateTime(timezone=True), server_default=func.now())
    creado_por     = Column(UUID(as_uuid=True), ForeignKey("usuarios.id"))

    gimnasio = relationship("Gimnasio", back_populates="ventas")
    miembro  = relationship("Miembro", back_populates="ventas")
    items    = relationship("VentaItem", back_populates="venta", cascade="all, delete-orphan")
    pagos    = relationship("Pago", back_populates="venta", cascade="all, delete-orphan")


class VentaItem(Base):
    __tablename__ = "venta_items"

    id              = Column(Integer, primary_key=True, index=True)
    venta_id        = Column(Integer, ForeignKey("ventas.id", ondelete="CASCADE"), nullable=False)
    # NULL = ítem libre (costo extra sin producto de catálogo detrás) — en ese
    # caso descripcion_libre trae el texto que escribió el staff.
    producto_id     = Column(Integer, ForeignKey("productos.id"), nullable=True)
    descripcion_libre = Column(String(200))
    cantidad        = Column(Integer, nullable=False)
    precio_unitario = Column(Numeric(10, 2), nullable=False)
    costo_unitario  = Column(Numeric(10, 2), nullable=False, default=0)  # precio_costo del producto al momento de la venta
    subtotal        = Column(Numeric(10, 2), nullable=False)
    notas           = Column(Text)  # observación puntual de este ítem (ej. motivo del costo extra)

    venta    = relationship("Venta", back_populates="items")
    producto = relationship("Producto", back_populates="venta_items")


# ─────────────────────────────────────────
# PAGOS (abonos de ventas)
# ─────────────────────────────────────────

class Pago(Base):
    __tablename__ = "pagos"

    id         = Column(Integer, primary_key=True, index=True)
    gym_id     = Column(UUID(as_uuid=True), ForeignKey("gimnasios.id", ondelete="CASCADE"), nullable=False)
    venta_id   = Column(Integer, ForeignKey("ventas.id", ondelete="CASCADE"), nullable=False)
    monto      = Column(Numeric(10, 2), nullable=False)
    metodo     = Column(Enum(MetodoPago), nullable=False, default=MetodoPago.efectivo)
    fecha      = Column(DateTime(timezone=True), server_default=func.now())
    notas      = Column(Text)

    venta = relationship("Venta", back_populates="pagos")


# ─────────────────────────────────────────
# GASTOS
# ─────────────────────────────────────────

class Gasto(Base):
    __tablename__ = "gastos"

    id          = Column(Integer, primary_key=True, index=True)
    gym_id      = Column(UUID(as_uuid=True), ForeignKey("gimnasios.id", ondelete="CASCADE"), nullable=False)
    categoria   = Column(String(100), nullable=False)
    descripcion = Column(Text)
    monto       = Column(Numeric(10, 2), nullable=False)
    fecha       = Column(DateTime(timezone=True), server_default=func.now())
    es_fijo     = Column(Boolean, default=False)
    creado_por  = Column(UUID(as_uuid=True), ForeignKey("usuarios.id"))

    gimnasio = relationship("Gimnasio", back_populates="gastos")


# ─────────────────────────────────────────
# PAGOS SAAS (suscripciones de los gyms a la plataforma)
# ─────────────────────────────────────────

class PagoSaas(Base):
    __tablename__ = "pagos_saas"

    id             = Column(Integer, primary_key=True, index=True)
    # RESTRICT y no CASCADE: esta es la facturación de la plataforma, no
    # datos del tenant. Borrar un gimnasio no puede llevarse puesto su
    # historial de ingresos — la DB tiene que rechazar ese borrado hasta
    # que alguien decida explícitamente qué hacer con estos registros.
    gym_id         = Column(UUID(as_uuid=True), ForeignKey("gimnasios.id", ondelete="RESTRICT"), nullable=False, index=True)
    plan           = Column(Enum(SaasPlan), nullable=False)
    monto          = Column(Numeric(10, 2), nullable=False)
    metodo         = Column(Enum(MetodoPago), nullable=False, default=MetodoPago.transferencia)
    referencia     = Column(String(200))   # número de transferencia bancaria
    estado         = Column(Enum(EstadoPagoSaas), nullable=False, default=EstadoPagoSaas.pendiente, index=True)
    notas          = Column(Text)          # notas del gym al solicitar (evidencia)
    # Foto del comprobante de transferencia, mismo patrón que
    # PagoMembresia.comprobante_url (migración 010) — nullable porque los
    # pagos ya confirmados antes de esta migración no lo tienen.
    comprobante_url = Column(String(300))
    # Nullable: la mayoría de los pagos son una renovación sin cambio de
    # tier. No-nulo = el gym pidió pasar a este tier — se aplica a
    # Gimnasio.saas_tier recién cuando el platform admin confirma este pago
    # (routes/suscripciones.py: confirmar_pago), nunca al solicitar.
    tier_solicitado = Column(Enum(SaasTier))
    razon_rechazo  = Column(Text)          # motivo del platform admin al rechazar
    solicitado_en  = Column(DateTime(timezone=True), server_default=func.now())
    confirmado_en  = Column(DateTime(timezone=True))
    confirmado_por = Column(String(200))   # identificador del superadmin

    gimnasio = relationship("Gimnasio", back_populates="pagos_saas")


# ─────────────────────────────────────────
# INSTRUCTORES
# ─────────────────────────────────────────

class Instructor(Base):
    __tablename__ = "instructores"

    id         = Column(Integer, primary_key=True, index=True)
    gym_id     = Column(UUID(as_uuid=True), ForeignKey("gimnasios.id", ondelete="CASCADE"), nullable=False, index=True)
    nombre     = Column(String(200), nullable=False)
    telefono   = Column(String(20))
    tipo       = Column(Enum(TipoInstructor), nullable=False)
    activo     = Column(Boolean, nullable=False, default=True)
    creado_en  = Column(DateTime(timezone=True), server_default=func.now())
    # NULL para instructores creados por el backfill de la migración 013 (no
    # había un admin real detrás de ese alta) — ver eliminar_instructor en
    # routes/instructores.py, que solo restringe el borrado cuando sí hay dueño.
    creado_por = Column(UUID(as_uuid=True), ForeignKey("usuarios.id"))

    clases = relationship("Clase", back_populates="instructor")


# ─────────────────────────────────────────
# CLASES (instancias de clases programadas)
# ─────────────────────────────────────────

class Clase(Base):
    __tablename__ = "clases"
    __table_args__ = (
        Index("ix_clases_gym_fecha", "gym_id", "fecha"),
    )

    id            = Column(Integer, primary_key=True, index=True)
    gym_id        = Column(UUID(as_uuid=True), ForeignKey("gimnasios.id", ondelete="CASCADE"), nullable=False)
    fecha         = Column(Date, nullable=False)
    hora_inicio   = Column(Time, nullable=False)
    hora_fin      = Column(Time, nullable=False)
    nombre        = Column(String(200), nullable=False)
    # Legado: texto libre pre-instructores. Ya no se escribe (ver instructor_id),
    # se deja sin tocar para no perder el historial de clases viejas.
    entrenador    = Column(String(200))
    instructor_id = Column(Integer, ForeignKey("instructores.id", ondelete="SET NULL"))
    capacidad     = Column(Integer, nullable=False, default=20)
    estado        = Column(Enum(EstadoClase), nullable=False, default=EstadoClase.programada)
    notas         = Column(Text)
    creado_en     = Column(DateTime(timezone=True), server_default=func.now())
    creado_por    = Column(UUID(as_uuid=True), ForeignKey("usuarios.id"))

    reservaciones = relationship("Reservacion", back_populates="clase", cascade="all, delete-orphan")
    asistencias   = relationship("Asistencia", back_populates="clase")
    instructor    = relationship("Instructor", back_populates="clases")


# ─────────────────────────────────────────
# RESERVACIONES
# ─────────────────────────────────────────

class Reservacion(Base):
    __tablename__ = "reservaciones"
    __table_args__ = (
        UniqueConstraint("clase_id", "miembro_id", name="uq_reservacion_clase_miembro"),
        Index("ix_reservaciones_gym_clase", "gym_id", "clase_id"),
    )

    id            = Column(Integer, primary_key=True, index=True)
    gym_id        = Column(UUID(as_uuid=True), ForeignKey("gimnasios.id", ondelete="CASCADE"), nullable=False)
    clase_id      = Column(Integer, ForeignKey("clases.id", ondelete="CASCADE"), nullable=False)
    miembro_id    = Column(Integer, ForeignKey("miembros.id"), nullable=False)
    estado        = Column(Enum(EstadoReservacion), nullable=False, default=EstadoReservacion.confirmada)
    canal         = Column(String(50), nullable=False, default="staff")
    reservado_en  = Column(DateTime(timezone=True), server_default=func.now())
    reservado_por = Column(UUID(as_uuid=True), ForeignKey("usuarios.id"))

    clase   = relationship("Clase", back_populates="reservaciones")
    miembro = relationship("Miembro")


# ─────────────────────────────────────────
# PAGOS DE MEMBRESÍA (abonos/cuotas)
# ─────────────────────────────────────────

class PagoMembresia(Base):
    __tablename__ = "pagos_membresia"

    id             = Column(Integer, primary_key=True, index=True)
    gym_id         = Column(UUID(as_uuid=True), ForeignKey("gimnasios.id", ondelete="CASCADE"), nullable=False)
    membresia_id   = Column(Integer, ForeignKey("membresias.id", ondelete="CASCADE"), nullable=False)
    monto          = Column(Numeric(10, 2), nullable=False)
    metodo         = Column(Enum(MetodoPago), nullable=False)
    fecha          = Column(DateTime(timezone=True), server_default=func.now())
    notas          = Column(Text)
    comprobante_url = Column(String(300))  # NULL: la mayoría de pagos en efectivo no tienen foto
    registrado_por = Column(UUID(as_uuid=True), ForeignKey("usuarios.id"))

    membresia = relationship("Membresia", back_populates="pagos")


# ─────────────────────────────────────────
# AUDIT LOG
# ─────────────────────────────────────────

class AuditLog(Base):
    __tablename__ = "audit_log"
    __table_args__ = (
        Index("ix_audit_gym_fecha",      "gym_id", "creado_en"),
        Index("ix_audit_tabla_registro", "tabla",  "registro_id"),
    )

    id          = Column(BigInteger, primary_key=True, autoincrement=True)
    # Sin ForeignKey a propósito, en los dos campos: un log de auditoría
    # tiene que sobrevivir aunque el gimnasio o el usuario referenciado se
    # borren después. Con FK (con o sin cascada), borrar un gimnasio fallaría
    # por su propio rastro de auditoría, o se lo llevaría puesto — ninguna
    # de las dos es aceptable para un historial forense. Referencia "blanda"
    # a propósito, no un olvido.
    gym_id      = Column(UUID(as_uuid=True), nullable=False)
    usuario_id  = Column(UUID(as_uuid=True))
    accion      = Column(String(10),  nullable=False)   # INSERT | UPDATE | DELETE
    tabla       = Column(String(100), nullable=False)
    registro_id = Column(String(100))
    payload     = Column(JSONB)
    ip          = Column(String(45))
    creado_en   = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)


# ─────────────────────────────────────────
# HISTORIAL MÉDICO (vertical rehab/clínica)
# ─────────────────────────────────────────

class HistorialMedico(Base):
    __tablename__ = "historial_medico"

    id          = Column(Integer, primary_key=True, index=True)
    gym_id      = Column(UUID(as_uuid=True), ForeignKey("gimnasios.id", ondelete="CASCADE"), nullable=False, index=True)
    paciente_id = Column(Integer, ForeignKey("miembros.id", ondelete="CASCADE"), nullable=False, index=True)
    tipo        = Column(Enum(TipoHistorialMedico), nullable=False)
    descripcion = Column(Text, nullable=False)
    fecha       = Column(Date)  # nullable: lesiones/operaciones viejas sin fecha exacta
    activa      = Column(Boolean, nullable=False, default=True)
    notas       = Column(Text)
    creado_en   = Column(DateTime(timezone=True), server_default=func.now())
    creado_por  = Column(UUID(as_uuid=True), ForeignKey("usuarios.id"), nullable=False)

    paciente = relationship("Miembro", back_populates="historial_medico")
