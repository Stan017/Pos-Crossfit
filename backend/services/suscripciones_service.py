"""
Lógica de negocio del estado de suscripción SaaS de un gimnasio.

Separado de auth.py: require_gym_activa es un gate de tenancy (¿tiene JWT
válido? ¿puede pasar?), no el lugar para la máquina de estados de billing.
"""
from datetime import date, datetime, timezone
from sqlalchemy.orm import Session
from models import Gimnasio, SaasEstado
from fecha import limite_gracia_en_utc

_DIAS_POR_VENCER = 7
# Días hábiles (lunes a sábado, domingo no cuenta) de prórroga después de
# saas_vence_en, con corte a las 12:00 hora Ecuador del último día. Ver
# fecha.limite_gracia_en_utc para el cálculo exacto del instante de corte.
_DIAS_GRACIA = 4


def calcular_saas_estado(gimnasio: Gimnasio, hoy: date) -> SaasEstado:
    """Calcula el estado correcto según fechas. No escribe en DB."""
    # Estados terminales: solo se escapan por acción explícita del platform admin.
    if gimnasio.saas_estado in (SaasEstado.suspendida, SaasEstado.vencida):
        return gimnasio.saas_estado

    if gimnasio.saas_estado == SaasEstado.trial:
        if gimnasio.saas_trial_hasta and gimnasio.saas_trial_hasta < hoy:
            return SaasEstado.vencida
        return SaasEstado.trial

    # activa / por_vencer / en_gracia: recalcular siempre desde saas_vence_en.
    if gimnasio.saas_vence_en is None:
        return SaasEstado.activa

    if gimnasio.saas_vence_en < hoy:
        # Ventana de gracia: sigue con acceso (en_gracia, no vencida) hasta
        # el corte exacto — después de eso pasa a vencida y ahí sí queda
        # terminal (ver chequeo de arriba) hasta acción del platform admin.
        if datetime.now(timezone.utc) < limite_gracia_en_utc(gimnasio.saas_vence_en, _DIAS_GRACIA):
            return SaasEstado.en_gracia
        return SaasEstado.vencida

    if (gimnasio.saas_vence_en - hoy).days <= _DIAS_POR_VENCER:
        return SaasEstado.por_vencer

    return SaasEstado.activa


def sincronizar_estado_saas_en_db(gimnasio: Gimnasio, db: Session) -> SaasEstado:
    """
    Recalcula el estado real del gimnasio y lo persiste si difiere del
    guardado (lazy — no hay job de fondo, se resincroniza en cada lectura).
    Side effect explícito: puede ejecutar un db.commit().
    """
    estado_correcto = calcular_saas_estado(gimnasio, date.today())
    if estado_correcto != gimnasio.saas_estado:
        gimnasio.saas_estado = estado_correcto
        db.commit()
    return gimnasio.saas_estado
