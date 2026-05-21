/**
 * Lhexia Guardián — polling GET /api/v1/owner/dashboard (v2 multiperfil)
 */
(function () {
  'use strict';

  var root = document.getElementById('ownerPwaApp');
  if (!root) return;

  var apiUrl = root.getAttribute('data-api-url') || '/api/v1/owner/dashboard';
  var pollMs = parseInt(root.getAttribute('data-poll-ms') || '45000', 10);
  var slotCaja = document.getElementById('ownerCardCaja');
  var slotInv = document.getElementById('ownerCardInventario');
  var statusEl = document.getElementById('ownerPwaLiveStatus');
  var greetingEl = document.getElementById('ownerGuardianGreeting');
  var iaBox = document.getElementById('ownerGuardianIa');
  var iaText = document.getElementById('ownerGuardianIaText');
  var consBox = document.getElementById('ownerGuardianConsolidado');
  var consMonto = document.getElementById('ownerGuardianConsolidadoMonto');
  var consDetalle = document.getElementById('ownerGuardianConsolidadoDetalle');
  var btnRefresh = document.getElementById('ownerBtnRefresh');
  var btnRefreshTop = document.getElementById('ownerBtnRefreshTop');
  var btnCall = document.getElementById('ownerBtnCall');
  var btnMic = document.getElementById('ownerBtnMic');
  var pollTimer = null;
  var lastMeta = {};

  function estadoClass(estado) {
    var e = (estado || 'verde').toLowerCase();
    if (e === 'rojo' || e === 'amarillo' || e === 'verde') return 'estado-' + e;
    return 'estado-verde';
  }

  function statusToEstado(status) {
    var m = { red: 'rojo', green: 'verde', amber: 'amarillo' };
    return m[(status || '').toLowerCase()] || 'verde';
  }

  function badgeLabel(estado) {
    var map = { verde: 'OK', amarillo: 'Atención', rojo: 'Alerta Crítica' };
    return map[(estado || '').toLowerCase()] || 'Estado';
  }

  function formatCardTitle(card, est) {
    var t = (card.titulo || '').trim();
    if (est !== 'rojo') return t;
    if (/alerta\s*crítica/i.test(t)) return t;
    if (/^caja/i.test(t)) return 'Alerta Crítica: Caja';
    if (/^inventario/i.test(t)) return 'Alerta Crítica: Inventario';
    return t.indexOf('Alerta') >= 0 ? t : 'Alerta Crítica: ' + t;
  }

  function renderCard(slot, card) {
    if (!slot || !card) return;
    var est = (card.estado || 'verde').toLowerCase();
    slot.className = 'owner-semaforo-card ' + estadoClass(est);
    slot.innerHTML =
      '<span class="owner-semaforo-badge">' + badgeLabel(est) + '</span>' +
      '<div class="owner-semaforo-title">' + escapeHtml(formatCardTitle(card, est)) + '</div>' +
      '<p class="owner-semaforo-msg">' + escapeHtml(card.mensaje || '') + '</p>' +
      '<div class="owner-semaforo-ts">' +
      '<span class="owner-live-dot" aria-hidden="true"></span>' +
      '<i class="fas fa-clock owner-semaforo-ts-icon" aria-hidden="true"></i>' +
      '<span class="owner-semaforo-ts-text">' + escapeHtml(card.timestamp || '') + '</span>' +
      '</div>';
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

  function updateCallButton(tel) {
    if (!btnCall) return;
    var phone = (tel != null ? String(tel) : '').trim();
    lastMeta.supervisor_telefono = phone;
    if (phone) {
      btnCall.href = 'tel:' + phone.replace(/\s/g, '');
      btnCall.classList.remove('disabled');
      btnCall.setAttribute('aria-disabled', 'false');
    } else {
      btnCall.href = '#';
      btnCall.classList.add('disabled');
      btnCall.setAttribute('aria-disabled', 'true');
    }
  }

  function applyGuardianPayload(data) {
    if (!data) return;

    if (greetingEl && data.saludo) {
      greetingEl.textContent = data.saludo;
    }

    if (iaBox && iaText) {
      var msg = (data.mensaje_ia || '').trim();
      if (msg) {
        iaText.textContent = msg;
        iaBox.classList.remove('d-none');
        iaBox.classList.toggle('owner-guardian-ia--alert', data.status_caja === 'red');
      } else {
        iaBox.classList.add('d-none');
      }
    }

    if (consBox && consMonto && consDetalle) {
      var c = data.consolidado || {};
      if (c.visible && c.descuadre_acumulado_fmt) {
        consMonto.textContent = c.descuadre_acumulado_fmt;
        var det = (c.cajas_con_descuadre || 0) + ' cierre(s) · ' +
          (c.sucursales_monitoreadas || 1) + ' sucursal(es)';
        consDetalle.textContent = det;
        consBox.classList.remove('d-none');
        consBox.classList.toggle(
          'owner-guardian-consolidado--danger',
          data.status_caja === 'red'
        );
      } else {
        consBox.classList.add('d-none');
      }
    }

    var tel = data.supervisor_telefono || (data.meta && data.meta.supervisor_telefono) || '';
    updateCallButton(tel);

    var critico = data.status_caja === 'red' || data.status_inventario === 'red';
    var ab = data.meta && data.meta.alertas_abiertas;
    var liveTxt = typeof ab === 'number'
      ? ab + ' alerta(s) operador'
      : (critico ? 'Atención requerida' : 'En línea');
    setLiveStatus(!critico || data.status_caja !== 'red', liveTxt);

    var perfil = data.perfil || 'guardian';
    document.title = 'Guardián · ' +
      (data.status_caja === 'red' ? 'Alerta' : (perfil === 'supervisor' ? 'Turno' : 'LhexIA'));
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
        var data = j.data;
        var cajaSlot = document.getElementById('ownerCardCaja');
        var invSlot = document.getElementById('ownerCardInventario');
        renderCard(cajaSlot, data.tarjeta_caja);
        renderCard(invSlot, data.tarjeta_inventario);
        lastMeta = data.meta || {};
        applyGuardianPayload(data);
      })
      .catch(function () {
        setLiveStatus(false, 'Error al cargar');
      });
  }

  function schedulePoll() {
    if (pollTimer) clearInterval(pollTimer);
    pollTimer = setInterval(fetchDashboard, Math.max(15000, pollMs));
  }

  function bindCardNavigation() {
    [slotCaja, slotInv].forEach(function (slot) {
      if (!slot || slot._ownerNavBound) return;
      var url = slot.getAttribute('data-nav-url');
      if (!url) return;
      slot.addEventListener('click', function () {
        window.location.href = url;
      });
      slot.addEventListener('keydown', function (ev) {
        if (ev.key === 'Enter' || ev.key === ' ') {
          ev.preventDefault();
          window.location.href = url;
        }
      });
      slot._ownerNavBound = true;
    });
  }

  function onRefreshClick(e) {
    if (e) e.preventDefault();
    fetchDashboard();
  }

  if (btnRefresh) btnRefresh.addEventListener('click', onRefreshClick);
  if (btnRefreshTop) btnRefreshTop.addEventListener('click', onRefreshClick);

  bindCardNavigation();

  if (btnMic) {
    btnMic.addEventListener('click', function () {
      if (window.bootstrap && document.getElementById('ownerMicToast')) {
        var t = new bootstrap.Toast(document.getElementById('ownerMicToast'));
        t.show();
      } else {
        alert('Agente de voz: próximamente en SD-2.');
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
      var standalone = window.matchMedia('(display-mode: standalone)').matches
        || window.matchMedia('(display-mode: fullscreen)').matches
        || window.navigator.standalone === true;
      if (!standalone) {
        navigator.serviceWorker.getRegistrations().then(function (regs) {
          regs.forEach(function (reg) { reg.unregister(); });
        });
        return;
      }
      navigator.serviceWorker.register('/owner-pwa/sw.js', { scope: '/' }).catch(function () {});
    });
  }

  fetchDashboard().then(schedulePoll);
})();
