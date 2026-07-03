/**
 * Caja prototipo — bienvenida kiosco, reloj, foco escaneo.
 */
(function () {
  'use strict';

  var STORAGE_KEY = 'cajaProtoWelcomeOk';

  function actualizarReloj() {
    var ahora = new Date();
    var elHora = document.getElementById('cajaProtoHora');
    var elFecha = document.getElementById('cajaProtoFecha');
    if (elHora) {
      elHora.textContent = ahora.toLocaleTimeString('es-CL', { hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: true });
    }
    if (elFecha) {
      elFecha.textContent = ahora.toLocaleDateString('es-CL', { weekday: 'long', day: 'numeric', month: 'long' });
    }
  }

  function intentarFullscreen() {
    var el = document.documentElement;
    if (!el.requestFullscreen) return;
    el.requestFullscreen().catch(function () {});
  }

  function mostrarBienvenida() {
    try {
      if (sessionStorage.getItem(STORAGE_KEY) === '1') return;
    } catch (e) {
      return;
    }
    var modalEl = document.getElementById('modalCajaProtoWelcome');
    if (!modalEl || typeof bootstrap === 'undefined') return;
    var modal = bootstrap.Modal.getOrCreateInstance(modalEl, { backdrop: 'static', keyboard: false });
    modal.show();
    var btn = document.getElementById('cajaProtoWelcomeOk');
    if (btn) {
      btn.addEventListener('click', function () {
        try { sessionStorage.setItem(STORAGE_KEY, '1'); } catch (e) {}
        modal.hide();
        intentarFullscreen();
        var wedge = document.getElementById('cajaBarcodeWedge');
        if (wedge) wedge.focus();
      }, { once: true });
    }
  }

  document.addEventListener('DOMContentLoaded', function () {
    actualizarReloj();
    setInterval(actualizarReloj, 1000);
    var montoInicial = document.getElementById('monto_inicial');
    if (montoInicial) {
      montoInicial.focus();
      return;
    }
    mostrarBienvenida();
    var wedge = document.getElementById('cajaBarcodeWedge');
    if (wedge && !document.getElementById('modalCajaProtoWelcome')) {
      wedge.focus();
    }
  });
})();
