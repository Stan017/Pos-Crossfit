# Política de Cookies — DarkCross

Última actualización: [FECHA — completar al publicar]

## Resumen

DarkCross usa únicamente **cookies técnicas necesarias para el
funcionamiento del sistema** (mantener tu sesión iniciada). No usamos
cookies de publicidad, ni de rastreo entre sitios, ni de terceros con
fines de análisis o marketing.

## Cookies que usamos

| Nombre | Propósito | Duración | Tipo |
|---|---|---|---|
| `cf_access` | Mantiene la sesión iniciada (token de acceso) | 30 minutos | Técnica, propia (first-party), httpOnly |
| `cf_refresh` | Renueva la sesión sin pedir login de nuevo | 30 días | Técnica, propia (first-party), httpOnly |

Ambas cookies:
- Son **`httpOnly`**: no pueden ser leídas por JavaScript, lo que reduce
  el riesgo de robo de sesión vía scripts maliciosos (XSS).
- Viajan solo por conexión cifrada (**`Secure`**, HTTPS) en producción.
- Son estrictamente necesarias para que la aplicación funcione — sin
  ellas, no es posible iniciar sesión ni mantenerla activa. Por eso no
  pedimos consentimiento de cookies para estas dos: son técnicas
  necesarias, no opcionales.

**[NOTA PARA EL ABOGADO]**: bajo la mayoría de marcos (LOPDP Ecuador
incluida) las cookies estrictamente necesarias para el funcionamiento
del servicio no requieren banner de consentimiento — solo informar su
uso, que es lo que hace este documento. Confirmar si aplica igual acá.

## Fuentes tipográficas (Google Fonts)

El sitio carga tipografías directamente desde los servidores de Google
(`fonts.googleapis.com`). Esto no es técnicamente una cookie, pero
implica que el navegador del visitante se conecta directamente a Google
para descargar esas fuentes, lo que expone su dirección IP a Google
según la propia política de privacidad de Google Fonts.

**[NOTA PARA EL ABOGADO]**: hay que decidir si esto amerita mención
aparte o si conviene migrar a fuentes auto-hospedadas para evitar esta
conexión de terceros por completo — es un cambio técnico simple si se
decide necesario.

## Lo que NO usamos

- Cookies de publicidad o remarketing.
- Cookies de analítica de terceros (Google Analytics, Meta Pixel, etc.)
  — no están instaladas en el sitio ni en la aplicación.
- Cookies de rastreo entre sitios distintos.

## Cómo desactivar las cookies

Podés bloquear o eliminar las cookies desde la configuración de tu
navegador. Si lo hacés, no vas a poder iniciar sesión ni usar la
aplicación — no es opcional para el funcionamiento del sistema.

## Contacto

infodarkcross@gmail.com
