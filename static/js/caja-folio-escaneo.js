/**
 * Caja — pistola / teclado: folio VL###### → abre modal Cobrar del vale.
 */
(function () {
  'use strict';

  function parseFolioVale(raw) {
    var s = String(raw || '').trim().toUpperCase();
    if (!s) return null;
    if (s.indexOf('VL') === 0) s = s.slice(2);
    s = s.replace(/^0+/, '') || '0';
    var n = parseInt(s, 10);
    return n > 0 ? n : null;
  }

  function abrirModalCobro(ventaId) {
    if (typeof bootstrap === 'undefined') return false;
    var el = document.getElementById('modalCobro' + ventaId);
    if (!el) return false;
    bootstrap.Modal.getOrCreateInstance(el).show();
    return true;
  }

  function flashCaja(msg, variant) {
    if (typeof window.mostrarPosToast === 'function') {
      window.mostrarPosToast(msg, { variant: variant || 'warning', delay: 3200 });
      return;
    }
    alert(msg);
  }

  function resaltarFila(ventaId) {
    var row = document.getElementById('cajaRowVale' + ventaId);
    if (!row) return;
    row.classList.add('caja-row-sla-attention');
    row.scrollIntoView({ block: 'nearest', behavior: 'smooth' });
  }

  async function buscarYAbrir(codigo) {
    var vid = parseFolioVale(codigo);
    if (!vid) {
      flashCaja('Folio inválido. Use VL001234 o el número del vale.', 'warning');
      return;
    }
    if (abrirModalCobro(vid)) {
      resaltarFila(vid);
      return;
    }
    var cfg = document.getElementById('caja-folio-config');
    var apiUrl = cfg && cfg.dataset && cfg.dataset.buscarUrl;
    if (!apiUrl) {
      flashCaja('Vale #' + vid + ' no está en la cola de cobro visible.', 'warning');
      return;
    }
    try {
      var url = apiUrl + (apiUrl.indexOf('?') >= 0 ? '&' : '?') + 'q=' + encodeURIComponent(codigo);
      var r = await fetch(url, { credentials: 'same-origin', headers: { Accept: 'application/json' } });
      var data = await r.json();
      if (data && data.ok && data.venta_id) {
        if (data.en_cola && abrirModalCobro(data.venta_id)) {
          resaltarFila(data.venta_id);
          return;
        }
        flashCaja(data.mensaje || 'Vale no disponible para cobro en esta pantalla.', 'warning');
        return;
      }
      flashCaja((data && data.mensaje) || 'Vale no encontrado.', 'warning');
    } catch (e) {
      flashCaja('Error al buscar vale. Intente de nuevo.', 'danger');
    }
  }

  document.addEventListener('DOMContentLoaded', function () {
    var wedge = document.getElementById('cajaBarcodeWedge');
    if (!wedge) return;

    wedge.addEventListener('keydown', function (e) {
      if (e.key !== 'Enter') return;
      e.preventDefault();
      var codigo = (wedge.value || '').replace(/\r/g, '').replace(/\n/g, '').trim();
      wedge.value = '';
      if (!codigo) return;
      buscarYAbrir(codigo);
    });

    document.addEventListener('click', function (ev) {
      var t = ev.target;
      if (!t || !t.closest) return;
      if (t.closest('.modal, .form-control, .form-select, button, a, input, textarea, select, label')) return;
      if (document.querySelector('.modal-premium.show')) return;
      try {
        wedge.focus({ preventScroll: true });
      } catch (err) {}
    });

    var params = new URLSearchParams(window.location.search || '');
    var autoCobrar = params.get('cobrar');
    if (autoCobrar) {
      setTimeout(function () {
        buscarYAbrir(autoCobrar);
        if (window.history && window.history.replaceState) {
          params.delete('cobrar');
          var qs = params.toString();
          window.history.replaceState({}, document.title, window.location.pathname + (qs ? '?' + qs : ''));
        }
      }, 400);
    }

    setTimeout(function () {
      try {
        wedge.focus({ preventScroll: true });
      } catch (err2) {}
    }, 300);
  });
})();
