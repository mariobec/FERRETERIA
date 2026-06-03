/**
 * Caja — reimpresión térmica directa (POST /api/pos/imprimir-ticket/<id>).
 */
(function () {
  'use strict';

  function aviso(msg, ok) {
    if (typeof window.mostrarPosToast === 'function') {
      window.mostrarPosToast(msg, { variant: ok ? 'success' : 'warning', delay: 4000 });
      return;
    }
    alert(msg);
  }

  document.addEventListener('click', function (ev) {
    var btn = ev.target && ev.target.closest ? ev.target.closest('.btn-caja-termica') : null;
    if (!btn) return;
    var vid = parseInt(btn.getAttribute('data-venta-id'), 10);
    if (!vid) return;
    ev.preventDefault();
    btn.disabled = true;
    fetch('/api/pos/imprimir-ticket/' + encodeURIComponent(vid), {
      method: 'POST',
      credentials: 'same-origin',
      headers: { 'Content-Type': 'application/json', Accept: 'application/json' },
      body: '{}',
    })
      .then(function (r) {
        return r.json().then(function (data) {
          return { ok: r.ok, data: data };
        });
      })
      .then(function (res) {
        var d = res.data || {};
        if (d.ok) {
          aviso('Ticket enviado a ' + (d.impresora || 'impresora térmica'), true);
        } else {
          aviso(d.mensaje || d.error || 'No se pudo imprimir en térmica.', false);
        }
      })
      .catch(function () {
        aviso('Error de red al imprimir. ¿Reinició Flask tras cambiar .env.local?', false);
      })
      .finally(function () {
        btn.disabled = false;
      });
  });
})();
