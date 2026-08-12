// Aviso de cookies — no hay botón "Rechazar" ni "Personalizar" a propósito:
// el sitio no usa cookies opcionales (nada de analytics, ads ni rastreo, ver
// cookie-policy.html), solo dos cookies técnicas de sesión que ni siquiera
// pone esta landing (las pone la app al loguear). Un banner de 3 botones
// prometería una opción de "rechazar" que no bloquearía nada real.
(function () {
  var KEY = 'darkcross_cookies_ack'
  if (localStorage.getItem(KEY)) return

  var banner = document.createElement('div')
  banner.setAttribute('role', 'region')
  banner.setAttribute('aria-label', 'Aviso de cookies')
  banner.className = 'fixed bottom-0 left-0 right-0 z-50 bg-surface border-t border-on-surface/[0.1] shadow-[0_-4px_16px_rgba(0,0,0,0.08)]'
  banner.innerHTML =
    '<div class="max-w-container-max-width mx-auto px-gutter py-4 flex flex-col sm:flex-row items-center gap-4">' +
      '<p class="font-body-sm text-on-surface-variant flex-1 text-center sm:text-left">' +
        'Usamos únicamente cookies técnicas necesarias para el funcionamiento del sistema — nada de publicidad ni rastreo. ' +
        '<a href="/cookie-policy.html" class="text-primary underline">Más información</a>' +
      '</p>' +
      '<button type="button" data-cookie-ack class="shrink-0 px-6 py-2.5 rounded-xl bg-primary text-on-primary font-bold hover:opacity-90 transition-opacity">' +
        'Entendido' +
      '</button>' +
    '</div>'

  document.body.appendChild(banner)

  banner.querySelector('[data-cookie-ack]').addEventListener('click', function () {
    localStorage.setItem(KEY, '1')
    banner.remove()
  })
})()
