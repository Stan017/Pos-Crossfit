-- Migración 026: comprobante de transferencia en pagos_saas + estado 'en_gracia'
--
-- Contexto: hasta ahora un pago de suscripción SaaS (pagos_saas) solo
-- guardaba texto libre (referencia/notas) como "evidencia" de una
-- transferencia — nunca una foto/comprobante real, a diferencia de
-- PagoMembresia que sí lo tiene desde la migración 010. Esto agrega el
-- mismo campo acá para que el platform admin pueda verificar la
-- transferencia de verdad antes de confirmar el pago.
--
-- También agrega 'en_gracia' al enum saas_estado: hasta ahora, el segundo
-- que saas_vence_en quedaba en el pasado, la cuenta pasaba a 'vencida' y
-- require_gym_activa bloqueaba con 402 sin ningún margen. Ahora hay una
-- ventana de gracia de 4 días hábiles (lunes a sábado, domingo no cuenta)
-- con corte a las 12:00 del cuarto día hábil, durante la cual la cuenta
-- muestra 'en_gracia' (visible, no oculto) y sigue teniendo acceso. La
-- lógica que decide cuándo aplica este estado vive en
-- services/suscripciones_service.py, no acá — esta migración solo habilita
-- el valor del enum.
--
-- ADVERTENCIA OPERATIVA: "ALTER TYPE ... ADD VALUE" no puede ejecutarse
-- dentro de un bloque de transacción explícito si el mismo script necesita
-- usar el valor nuevo después. Si tu cliente SQL envuelve todo el archivo
-- en una sola transacción y esto falla con "cannot run inside a transaction
-- block", corré esta línea sola, primero, y el resto del archivo después.

ALTER TABLE pagos_saas
    ADD COLUMN IF NOT EXISTS comprobante_url VARCHAR(300);

ALTER TYPE saasestado ADD VALUE IF NOT EXISTS 'en_gracia';
