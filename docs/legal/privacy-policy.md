# Política de Privacidad — DarkCross

Última actualización: [FECHA — completar al publicar]

## 1. Quiénes somos

DarkCross es un software como servicio (SaaS) que opera dos productos:
un sistema de gestión para boxes de CrossFit/gimnasios y un sistema de
gestión para clínicas de rehabilitación traumatológica. Contacto:
infodarkcross@gmail.com.

**[NOTA PARA EL ABOGADO]**: falta la razón social/persona jurídica bajo la
cual opera DarkCross (persona natural con RUC, sociedad constituida,
etc.) y el domicilio legal en Ecuador. Esta política no puede publicarse
sin ese dato — es obligatorio identificarlo como responsable del
tratamiento.

## 2. Dos roles distintos frente a los datos

Esto es estructuralmente importante y el abogado debería confirmarlo
explícitamente:

- **Cuando el dato es de un gimnasio o clínica que contrata DarkCross**
  (nombre del negocio, email de contacto, credenciales de acceso de su
  personal): DarkCross es el **responsable del tratamiento**.
- **Cuando el dato es de un miembro/paciente que el gimnasio o clínica
  carga en el sistema** (nombre, cédula, teléfono, historial médico,
  comprobantes de pago): el gimnasio o clínica es el **responsable del
  tratamiento**, y DarkCross actúa como **encargado del tratamiento** —
  solo procesamos esos datos por instrucción y en nombre de nuestro
  cliente (el gym/clínica), no somos quien decide para qué se usan.

**[NOTA PARA EL ABOGADO]**: esto normalmente requiere un contrato de
encargo de tratamiento (DPA) separado entre DarkCross y cada
gimnasio/clínica cliente, no solo esta política pública. Hoy no existe
ese contrato — falta redactarlo.

## 3. Qué datos recopilamos

### 3.1 De la persona que administra la cuenta del gimnasio/clínica (`Usuario`)
Nombre, apellido, email, fecha de nacimiento, contraseña (almacenada
como hash, nunca en texto plano), rol dentro del sistema.

### 3.2 Del gimnasio o clínica como negocio (`Gimnasio`)
Nombre comercial, slug/identificador único, email, RUC, dirección y
teléfono (estos últimos, opcionales, usados para las facturas que emite
el propio gym/clínica a sus clientes).

### 3.3 De los miembros o pacientes del gimnasio/clínica (`Miembro`)
Nombre, apellido, email, teléfono, cédula, fecha de nacimiento, contacto
de emergencia, peso, altura, foto de perfil, notas libres cargadas por
el staff.

### 3.4 Datos de salud (solo vertical clínica/rehabilitación)
Patologías, lesiones previas, operaciones previas, y notas de evolución
por sesión de terapia. **Esta es una categoría de dato sensible bajo la
LOPDP de Ecuador (y equivalentes internacionales) — requiere base legal
reforzada y medidas de seguridad adicionales.**

**[NOTA PARA EL ABOGADO]**: hoy el sistema no pide un consentimiento
explícito y separado al paciente antes de que el gimnasio/clínica cargue
sus datos de salud — ese consentimiento, si es necesario, lo debe
obtener el gimnasio/clínica directamente del paciente, no DarkCross. Hay
que confirmar si esta política debe decirlo así de explícito.

### 3.5 Comprobantes de pago
Imágenes de comprobantes de transferencia que el staff sube al
registrar un pago de membresía. Pueden contener datos bancarios
parciales visibles en la imagen (número de cuenta origen, por ejemplo).

### 3.6 Datos técnicos
Dirección IP y marca de tiempo de cada acción relevante (registro de
auditoría interno, con fines de seguridad y trazabilidad — quién hizo
qué y cuándo dentro de la cuenta del gym/clínica).

### 3.7 Cookies de sesión
Ver la Política de Cookies. En resumen: dos cookies técnicas
(autenticación), ninguna de rastreo o publicidad.

## 4. Para qué usamos los datos

- Operar el software: login, gestión de miembros/pacientes, membresías,
  clases/citas, cobros, inventario, reportes financieros.
- Seguridad: prevenir accesos no autorizados, investigar incidentes.
- Comunicación: responder consultas de soporte enviadas por el
  gym/clínica.
- **No vendemos datos a terceros. No usamos los datos para publicidad
  propia ni de terceros. No hay rastreo publicitario ni analítica de
  terceros en la plataforma.**

## 5. Con quién compartimos los datos (subencargados / proveedores de infraestructura)

Los datos se almacenan y procesan a través de los siguientes
proveedores, todos con presencia en Estados Unidos:

- **Base de datos**: Supabase (PostgreSQL), infraestructura en AWS,
  región us-east-1 (Virginia, EE.UU.).
- **Backend/API**: Google Cloud Run (Google Cloud Platform, EE.UU.).
- **Frontend**: Vercel (EE.UU.).
- **Fuentes tipográficas**: Google Fonts — el navegador del visitante se
  conecta directamente a servidores de Google para cargar las
  tipografías del sitio, lo que expone la IP del visitante a Google.
- **WhatsApp Business**: si el visitante usa el botón de WhatsApp del
  sitio, la conversación pasa a ser gestionada por Meta/WhatsApp bajo
  sus propias políticas.

**[NOTA PARA EL ABOGADO]**: esto implica transferencia internacional de
datos (Ecuador → EE.UU.). Bajo la LOPDP hay que evaluar si aplica algún
mecanismo de transferencia (cláusulas contractuales, etc.) o si basta
con informarlo aquí. Ninguno de estos proveedores tiene hoy un acuerdo
de procesamiento de datos firmado con DarkCross — son simplemente los
proveedores de infraestructura que usamos.

## 6. Cuánto tiempo conservamos los datos

**[NOTA PARA EL ABOGADO / PENDIENTE DE DEFINIR]**: hoy el producto no
tiene un mecanismo automático de purga de datos por antigüedad. Los
datos de un gimnasio/clínica se conservan mientras la cuenta esté
activa, y quedan en la base de datos hasta que se pida su eliminación
manual. Esto hay que definirlo formalmente (ej. "N días después de
cancelar la suscripción") antes de publicar la política, y
eventualmente construir el mecanismo técnico que lo cumpla.

## 7. Derechos del titular de los datos

Bajo la LOPDP de Ecuador, toda persona tiene derecho a acceder,
rectificar, actualizar, eliminar (derecho al olvido) y oponerse al
tratamiento de sus datos personales, así como a la portabilidad de los
mismos. Para ejercerlos, contactar a infodarkcross@gmail.com.

**Importante**: si tus datos fueron cargados por un gimnasio o clínica
que usa DarkCross (sos un miembro o paciente, no el dueño de la cuenta),
la vía correcta para ejercer estos derechos es contactar directamente a
ese gimnasio/clínica — es quien decide qué datos tuyos existen en el
sistema. DarkCross puede colaborar técnicamente, pero no es quien
autoriza el cambio.

## 8. Seguridad

Contraseñas almacenadas con hash (nunca en texto plano). Comunicación
cifrada (HTTPS) entre el navegador y el servidor. Aislamiento de datos
por cliente (multi-tenant): cada gimnasio/clínica solo puede ver y
modificar sus propios datos, reforzado a nivel de base de datos
(Row-Level Security), no solo a nivel de aplicación.

## 9. Cambios a esta política

Podemos actualizar esta política. Los cambios materiales se
notificarán por email a los administradores de cuenta.

## 10. Contacto

infodarkcross@gmail.com
