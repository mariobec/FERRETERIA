/**
 * PWA Dueño — polling GET /api/v1/owner/dashboard
 */
(function () {
  'use strict';

  var root = document.getElementById('ownerPwaApp');
  if (!root) return;

  var apiUrl = root.getAttribute('data-api-url') || '/api/v1/owner/dashboard';
  var pollMs = parseInt(root.getAttribute('data-poll-ms') || '45000', 10);
  var ccUrl = root.getAttribute('data-cc-url') || '/admin/control-center';
  var slotCaja = document.getElementById('ownerCardCaja');
  var slotInv = document.getElementById('ownerCardInventario');
  var statusEl = document.getElementById('ownerPwaLiveStatus');
  var btnRefresh = document.getElementById('ownerBtnRefresh');
  var btnCall = document.getElementById('ownerBtnCall');
  var btnMic = document.getElementById('ownerBtnMic');
  var pollTimer = null;
  var lastMeta = {};

  function estadoClass(estado) {
    var e = (estado || 'verde').toLowerCase();
    if (e === 'rojo' || e === 'amarillo' || e === 'verde') return 'estado-' + e;
    return 'estado-verde';
  }

  function badgeLabel(estado) {
    var map = { verde: 'OK', amarillo: 'Atención', rojo: 'Alerta' };
    return map[(estado || '').toLowerCase()] || 'Estado';
  }

  function renderCard(slot, card) {
    if (!slot || !card) return;
    var est = (card.estado || 'verde').toLowerCase();
    slot.className = 'owner-semaforo-card ' + estadoClass(est);
    slot.innerHTML =
      '<span class="owner-semaforo-badge">' + badgeLabel(est) + '</span>' +
      '<div class="owner-semaforo-title">' + escapeHtml(card.titulo || '') + '</div>' +
      '<p class="owner-semaforo-msg">' + escapeHtml(card.mensaje || '') + '</p>' +
      '<div class="owner-semaforo-ts"><i class="fas fa-clock me-1"></i>' + escapeHtml(card.timestamp || '') + '</div>';
    slot.dataset.accion = card.accion_requerida ? '1' : '0';
    slot.dataset.tipoAccion = card.tipo_accion || '';
  }

  function escapeHtml(s) {
    var d = document.createElement('div');
    d.textContent = String(s);
    return d.innerHTML;
  }

  function setLiveStatus(ok, text) {
    if (!statusEl) return;
    var dot = statusEl.querySelector('.owner-pwa-status-dot');
    if (dot) {
      dot.classList.toggle('ok', !!ok);
      dot.classList.toggle('err', !ok);
    }
    var span = statusEl.querySelector('.owner-pwa-status-text');
    if (span) span.textContent = text || (ok ? 'En línea' : 'Sin conexión');
  }

  function updateCallButton(meta) {
    if (!btnCall) return;
    var tel = (meta && meta.supervisor_telefono) ? String(meta.supervisor_telefono).trim() : '';
    lastMeta.supervisor_telefono = tel;
    if (tel) {
      btnCall.href = 'tel:' + tel.replace(/\s/g, '');
      btnCall.classList.remove('disabled');
      btnCall.setAttribute('aria-disabled', 'false');
    } else {
      btnCall.href = '#';
      btnCall.classList.add('disabled');
      btnCall.setAttribute('aria-disabled', 'true');
    }
  }

  function showSkeleton() {
    if (slotCaja) slotCaja.outerHTML = '<div class="owner-pwa-skeleton mb-3" id="ownerCardCaja"></div>';
    if (slotInv) slotInv.outerHTML = '<div class="owner-pwa-skeleton mb-3" id="ownerCardInventario"></div>';
  }

  function fetchDashboard() {
    var url = apiUrl + (apiUrl.indexOf('?') >= 0 ? '&' : '?') + 'nocache=1';
    setLiveStatus(true, 'Actualizando…');
    return fetch(url, {
      method: 'GET',
      credentials: 'same-origin',
      headers: { Accept: 'application/json' },
    })
      .then(function (r) {
        if (r.status === 401) {
          window.location.href = '/login?next=' + encodeURIComponent('/owner-mobile');
          throw new Error('login_required');
        }
        if (!r.ok) throw new Error('http_' + r.status);
        return r.json();
      })
      .then(function (j) {
        if (!j || j.status !== 'success' || !j.data) throw new Error('invalid_payload');
        var cajaSlot = document.getElementById('ownerCardCaja');
        var invSlot = document.getElementById('ownerCardInventario');
        renderCard(cajaSlot, j.data.tarjeta_caja);
        renderCard(invSlot, j.data.tarjeta_inventario);
        lastMeta = j.data.meta || {};
        updateCallButton(lastMeta);
        var ab = lastMeta.alertas_abiertas;
        setLiveStatus(true, typeof ab === 'number' ? ab + ' alerta(s) operador' : 'En línea');
        document.title = 'Dueño · ' + (j.data.tarjeta_caja && j.data.tarjeta_caja.estado === 'rojo' ? 'Alerta' : 'LhexIA');
      })
      .catch(function () {
        setLiveStatus(false, 'Error al cargar');
      });
  }

  function schedulePoll() {
    if (pollTimer) clearInterval(pollTimer);
    pollTimer = setInterval(fetchDashboard, Math.max(15000, pollMs));
  }

  if (btnRefresh) {
    btnRefresh.addEventListener('click', function (e) {
      e.preventDefault();
      fetchDashboard();
    });
  }

  if (btnMic) {
    btnMic.addEventListener('click', function () {
      if (window.bootstrap && document.getElementById('ownerMicToast')) {
        var t = new bootstrap.Toast(document.getElementById('ownerMicToast'));
        t.show();
      } else {
        alert('Control por voz: próximamente en SD-2.');
      }
    });
  }

  if (btnCall) {
    btnCall.addEventListener('click', function (e) {
      if (!lastMeta.supervisor_telefono) {
        e.preventDefault();
        alert('Configure OWNER_SUPERVISOR_TELEFONO en el servidor para llamar al supervisor.');
      }
    });
  }

  if ('serviceWorker' in navigator) {
    window.addEventListener('load', function () {
      navigator.serviceWorker.register('/owner-pwa/sw.js', { scope: '/' }).catch(function () {});
    });
  }

  fetchDashboard().then(schedulePoll);
})();
