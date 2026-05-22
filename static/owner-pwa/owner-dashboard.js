/**
 * Lhexia Guardián v3 — Ecosistema VERTEX · dashboard, acciones, feed y KPIs
 */
(function () {
  'use strict';

  var root = document.getElementById('ownerPwaApp');
  if (!root) return;

  var apiUrl = root.getAttribute('data-api-url') || '/api/v1/owner/dashboard';
  var pollMs = parseInt(root.getAttribute('data-poll-ms') || '45000', 10);
  var cardsMount = document.getElementById('ownerGuardianCards');
  var ccUrl = (cardsMount && cardsMount.getAttribute('data-cc-url')) || '/admin/control-center';
  var invUrl = (cardsMount && cardsMount.getAttribute('data-inv-url')) || '/ia/abastecimiento?dias=30&solo_alerta=1&from=owner';

  var DOMINIO_SLOT = {
    caja: 'ownerCardCaja',
    inventario: 'ownerCardInventario',
    credito: 'ownerCardCredito',
    compras: 'ownerCardCompras',
  };

  var NAV_DEFAULT = {
    caja: ccUrl,
    inventario: invUrl,
    credito: '/creditos',
    compras: '/compras/ordenes',
  };

  var statusEl = document.getElementById('ownerPwaLiveStatus');
  var greetingEl = document.getElementById('ownerGuardianGreeting');
  var iaBox = document.getElementById('ownerGuardianIa');
  var iaText = document.getElementById('ownerGuardianIaText');
  var ventasBox = document.getElementById('ownerGuardianVentas');
  var ventasMonto = document.getElementById('ownerGuardianVentasMonto');
  var ventasVar = document.getElementById('ownerGuardianVentasVar');
  var consBox = document.getElementById('ownerGuardianConsolidado');
  var consMonto = document.getElementById('ownerGuardianConsolidadoMonto');
  var consDetalle = document.getElementById('ownerGuardianConsolidadoDetalle');
  var consKicker = document.getElementById('ownerGuardianConsolidadoKicker');
  var statusRing = document.getElementById('ownerGuardianStatusRing');
  var statusRingLabel = document.getElementById('ownerGuardianStatusRingLabel');
  var establecimientoEl = document.getElementById('ownerGuardianEstablecimiento');
  var actualizadoEl = document.getElementById('ownerGuardianActualizado');
  var feedList = document.getElementById('ownerGuardianFeed');
  var feedEmpty = document.getElementById('ownerGuardianFeedEmpty');
  var semMini = document.getElementById('ownerGuardianSemMini');

  var DOMINIO_LABEL = { caja: 'Caja', inventario: 'Inv', credito: 'Créd', compras: 'OC' };
  var DOMINIO_ICON = {
    caja: 'fa-cash-register',
    inventario: 'fa-boxes-stacked',
    credito: 'fa-file-invoice-dollar',
    compras: 'fa-truck',
  };
  var FEED_AGENT_ICON = { critical: 'fa-triangle-exclamation', warning: 'fa-circle-exclamation', info: 'fa-circle-info' };
  var btnRefresh = document.getElementById('ownerBtnRefresh');
  var btnRefreshTop = document.getElementById('ownerBtnRefreshTop');
  var btnCall = document.getElementById('ownerBtnCall');
  var btnMic = document.getElementById('ownerBtnMic');
  var pollTimer = null;
  var lastMeta = {};
  var boundSlots = {};

  function bootstrapHeroFromSsr() {
    var fmt = (root.getAttribute('data-ventas-fmt') || '').trim();
    if (!fmt || !ventasMonto) return;
    ventasMonto.textContent = fmt;
    if (ventasVar) {
      var vRaw = root.getAttribute('data-var-pct');
      var tx = parseInt(root.getAttribute('data-transacciones') || '0', 10);
      if (vRaw !== '' && vRaw != null && !isNaN(parseFloat(vRaw))) {
        var v = parseFloat(vRaw);
        var sign = v > 0 ? '+' : '';
        ventasVar.textContent = sign + v + '% vs ayer · ' + tx + ' ventas';
        ventasVar.classList.toggle('owner-guardian-ventas-var--up', v > 0);
        ventasVar.classList.toggle('owner-guardian-ventas-var--down', v < 0);
      }
    }
    if (ventasBox) ventasBox.classList.remove('d-none');
  }
  bootstrapHeroFromSsr();

  function estadoClass(estado) {
    var e = (estado || 'verde').toLowerCase();
    if (e === 'rojo' || e === 'amarillo' || e === 'verde') return 'estado-' + e;
    return 'estado-verde';
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
    if (/^cr[eé]dito/i.test(t)) return 'Alerta Crítica: Crédito';
    if (/^compras/i.test(t)) return 'Alerta Crítica: Compras';
    return t.indexOf('Alerta') >= 0 ? t : 'Alerta Crítica: ' + t;
  }

  function escapeHtml(s) {
    var d = document.createElement('div');
    d.textContent = String(s);
    return d.innerHTML;
  }

  function actionsHtml(acciones) {
    if (!acciones || !acciones.length) return '';
    var html = '<div class="owner-card-actions-inner">';
    acciones.forEach(function (a) {
      var cls = 'btn btn-sm owner-card-action';
      if (a.tipo === 'tel') cls += ' owner-card-action--tel';
      var tag = a.tipo === 'nav' ? 'a' : 'a';
      var href = escapeHtml(a.href || '#');
      var label = escapeHtml(a.label || 'Acción');
      html += '<' + tag + ' class="' + cls + '" href="' + href + '" data-action-tipo="' +
        escapeHtml(a.tipo || 'nav') + '">' + label + '</' + tag + '>';
    });
    html += '</div>';
    return html;
  }

  function renderCardBody(slot, card) {
    if (!slot || !card) return;
    var est = (card.estado || 'verde').toLowerCase();
    var dominio = card.dominio || slot.getAttribute('data-dominio') || '';
    slot.className = 'owner-semaforo-card ' + estadoClass(est);
    if (dominio) slot.setAttribute('data-dominio', dominio);
    slot.classList.remove('d-none');

    var nav = NAV_DEFAULT[dominio] || slot.getAttribute('data-nav-url') || ccUrl;
    var firstNav = (card.acciones || []).find(function (a) { return a.tipo === 'nav'; });
    if (firstNav && firstNav.href) nav = firstNav.href;
    slot.setAttribute('data-nav-url', nav);

    slot.innerHTML =
      '<span class="owner-semaforo-badge">' + badgeLabel(est) + '</span>' +
      '<div class="owner-semaforo-title">' +
      (DOMINIO_ICON[dominio] ? '<i class="fas ' + DOMINIO_ICON[dominio] + ' me-1" aria-hidden="true"></i>' : '') +
      escapeHtml(formatCardTitle(card, est)) + '</div>' +
      '<p class="owner-semaforo-msg">' + escapeHtml(card.mensaje || '') + '</p>' +
      '<div class="owner-semaforo-ts">' +
      '<span class="owner-live-dot" aria-hidden="true"></span>' +
      '<i class="fas fa-clock owner-semaforo-ts-icon" aria-hidden="true"></i>' +
      '<span class="owner-semaforo-ts-text">' + escapeHtml(card.timestamp || '') + '</span>' +
      '</div>' +
      '<div class="owner-card-actions" data-actions-mount>' + actionsHtml(card.acciones) + '</div>' +
      '<span class="owner-card-chevron" aria-hidden="true"><i class="fas fa-chevron-right"></i></span>';

    slot.dataset.accion = card.accion_requerida ? '1' : '0';
    slot.dataset.tipoAccion = card.tipo_accion || '';
    bindSlot(slot);
  }

  function bindSlot(slot) {
    if (!slot || boundSlots[slot.id]) return;
    slot.setAttribute('role', 'button');
    slot.setAttribute('tabindex', '0');
    slot.addEventListener('click', function (ev) {
      if (ev.target.closest('.owner-card-action')) return;
      var url = slot.getAttribute('data-nav-url');
      if (url) window.location.href = url;
    });
    slot.addEventListener('keydown', function (ev) {
      if (ev.key === 'Enter' || ev.key === ' ') {
        ev.preventDefault();
        var url = slot.getAttribute('data-nav-url');
        if (url) window.location.href = url;
      }
    });
    var actions = slot.querySelectorAll('.owner-card-action');
    actions.forEach(function (btn) {
      btn.addEventListener('click', function (ev) {
        ev.stopPropagation();
        if (btn.getAttribute('data-action-tipo') === 'tel' && !btn.getAttribute('href').replace('tel:', '').trim()) {
          ev.preventDefault();
        }
      });
    });
    boundSlots[slot.id] = true;
  }

  function renderMiniSemaforos(data) {
    if (!semMini) return;
    var list = data.tarjetas;
    if (!list || !list.length) {
      list = [];
      if (data.tarjeta_caja) list.push(Object.assign({ dominio: 'caja' }, data.tarjeta_caja));
      if (data.tarjeta_inventario) list.push(Object.assign({ dominio: 'inventario' }, data.tarjeta_inventario));
      if (data.tarjeta_credito) list.push(Object.assign({ dominio: 'credito' }, data.tarjeta_credito));
      if (data.tarjeta_compras) list.push(Object.assign({ dominio: 'compras' }, data.tarjeta_compras));
    }
    semMini.innerHTML = '';
    list.forEach(function (card) {
      var dom = card.dominio || '';
      var est = (card.estado || 'verde').toLowerCase();
      var slotId = DOMINIO_SLOT[dom];
      var slot = slotId ? document.getElementById(slotId) : null;
      var href = (card.acciones || []).find(function (a) { return a.tipo === 'nav'; });
      href = (href && href.href) || (slot && slot.getAttribute('data-nav-url')) || NAV_DEFAULT[dom] || ccUrl;
      var a = document.createElement('a');
      a.className = 'owner-guardian-sem-mini__chip owner-guardian-sem-mini__chip--' + est;
      a.href = href;
      a.setAttribute('aria-label', (DOMINIO_LABEL[dom] || dom) + ' ' + est);
      a.innerHTML =
        '<span class="owner-guardian-sem-mini__dot" aria-hidden="true"></span>' +
        '<span>' + escapeHtml(DOMINIO_LABEL[dom] || dom) + '</span>';
      a.addEventListener('click', function (ev) {
        ev.preventDefault();
        if (slot) slot.scrollIntoView({ behavior: 'smooth', block: 'start' });
        else window.location.href = href;
      });
      semMini.appendChild(a);
    });
  }

  function renderTarjetas(data) {
    var list = data.tarjetas;
    if (!list || !list.length) {
      renderCardBody(document.getElementById('ownerCardCaja'), data.tarjeta_caja);
      renderCardBody(document.getElementById('ownerCardInventario'), data.tarjeta_inventario);
      if (data.tarjeta_credito) renderCardBody(document.getElementById('ownerCardCredito'), data.tarjeta_credito);
      if (data.tarjeta_compras) renderCardBody(document.getElementById('ownerCardCompras'), data.tarjeta_compras);
      return;
    }
    list.forEach(function (card) {
      var dom = card.dominio || '';
      var id = DOMINIO_SLOT[dom];
      var slot = id ? document.getElementById(id) : null;
      if (slot) renderCardBody(slot, card);
    });
  }

  function formatActualizado(iso) {
    if (!iso) return '';
    try {
      var d = new Date(iso);
      if (isNaN(d.getTime())) return '';
      return 'Actualizado ' + d.toLocaleTimeString('es-CL', { hour: '2-digit', minute: '2-digit' });
    } catch (e) {
      return '';
    }
  }

  function renderStatusRing(data) {
    if (!statusRing || !statusRingLabel) return;
    var st = (data.status_global || 'green').toLowerCase();
    statusRing.className = 'owner-guardian-status-ring owner-guardian-status-ring--' +
      (st === 'red' ? 'red' : st === 'amber' ? 'amber' : 'green');
    var labels = { red: 'Alerta', amber: 'Atención', green: 'Estable' };
    statusRingLabel.textContent = labels[st] || 'OK';
  }

  function renderFeed(items) {
    if (!feedList) return;
    feedList.innerHTML = '';
    if (!items || !items.length) {
      if (feedEmpty) feedEmpty.classList.remove('d-none');
      return;
    }
    if (feedEmpty) feedEmpty.classList.add('d-none');
    items.forEach(function (it) {
      var li = document.createElement('li');
      var sev = (it.severidad || 'info').toLowerCase();
      if (sev !== 'critical' && sev !== 'warning') sev = 'info';
      li.className = 'owner-guardian-feed-item owner-guardian-feed-item--' + sev;
      var href = it.nav_href || ccUrl;
      var icon = FEED_AGENT_ICON[sev] || 'fa-bolt';
      li.innerHTML =
        '<a href="' + escapeHtml(href) + '" class="owner-guardian-feed-link">' +
        '<span class="owner-guardian-feed-agent" aria-hidden="true"><i class="fas ' + icon + '"></i></span>' +
        '<span class="owner-guardian-feed-body">' +
        '<span class="owner-guardian-feed-item-title">' + escapeHtml(it.titulo || '') + '</span>' +
        '<span class="owner-guardian-feed-meta">' + escapeHtml(it.hace || 'Ahora') + '</span>' +
        (it.codigo ? '<span class="owner-guardian-feed-codigo">' + escapeHtml(it.codigo) + '</span>' : '') +
        '</span>' +
        '<i class="fas fa-chevron-right owner-guardian-feed-chevron" aria-hidden="true"></i>' +
        '</a>';
      feedList.appendChild(li);
    });
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

    if (greetingEl && data.saludo) greetingEl.textContent = data.saludo;

    if (iaBox && iaText) {
      var msg = (data.mensaje_ia || '').trim();
      if (msg) {
        iaText.textContent = msg;
        iaBox.classList.remove('d-none');
        iaBox.classList.toggle('owner-guardian-ia--alert', data.status_global === 'red');
      } else {
        iaBox.classList.add('d-none');
      }
    }

    var c = data.consolidado || {};
    if (ventasBox && ventasMonto && ventasVar) {
      if (c.ventas_hoy_fmt) {
        ventasMonto.textContent = c.ventas_hoy_fmt;
        var v = c.var_vs_ayer_pct;
        if (v != null && v !== '') {
          var sign = v > 0 ? '+' : '';
          ventasVar.textContent = sign + v + '% vs ayer · ' + (c.transacciones_hoy || 0) + ' ventas';
          ventasVar.classList.toggle('owner-guardian-ventas-var--up', v > 0);
          ventasVar.classList.toggle('owner-guardian-ventas-var--down', v < 0);
        } else {
          ventasVar.textContent = (c.transacciones_hoy || 0) + ' transacciones hoy';
        }
        ventasBox.classList.remove('d-none');
      } else if (!root.getAttribute('data-ventas-fmt')) {
        ventasBox.classList.add('d-none');
      }
    }

    if (consKicker && c.desfalco_kicker) {
      consKicker.textContent = c.desfalco_kicker;
    }
    if (consBox && consMonto && consDetalle) {
      if (c.visible && c.descuadre_acumulado_fmt) {
        consMonto.textContent = c.descuadre_acumulado_fmt;
        consDetalle.textContent =
          c.desfalco_detalle ||
          ((c.cajas_con_descuadre || 0) + ' cierre(s) con diferencia');
        consBox.classList.remove('d-none');
        consBox.classList.toggle('owner-guardian-consolidado--danger', data.status_caja === 'red');
      } else {
        consBox.classList.add('d-none');
      }
    }

    if (establecimientoEl) {
      var estLabel = (c.establecimiento_label || (data.meta && data.meta.establecimiento_label) || '').trim();
      if (estLabel) establecimientoEl.textContent = estLabel;
    }
    if (actualizadoEl && data.meta && data.meta.generado_en) {
      actualizadoEl.textContent = formatActualizado(data.meta.generado_en);
    }

    renderStatusRing(data);
    renderFeed(data.feed_preview || []);

    var tel = data.supervisor_telefono || (data.meta && data.meta.supervisor_telefono) || '';
    updateCallButton(tel);

    var critico = data.status_global === 'red' || data.status_caja === 'red';
    var ab = data.meta && data.meta.alertas_abiertas;
    var liveTxt = typeof ab === 'number'
      ? ab + ' alerta(s) operador'
      : (critico ? 'Atención requerida' : 'En línea');
    setLiveStatus(data.status_global !== 'red', liveTxt);

    document.title = 'Guardián · ' + (data.status_global === 'red' ? 'Alerta' : 'LhexIA');
  }

  function fetchDashboard() {
    var url = apiUrl + (apiUrl.indexOf('?') >= 0 ? '&' : '?') + 'nocache=1&v=3';
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
        renderTarjetas(data);
        renderMiniSemaforos(data);
        lastMeta = data.meta || {};
        applyGuardianPayload(data);
      })
      .catch(function () {
        setLiveStatus(false, 'Error al cargar');
      });
  }

  function onRefreshClick(e) {
    if (e) e.preventDefault();
    fetchDashboard();
  }

  if (btnRefresh) btnRefresh.addEventListener('click', onRefreshClick);
  if (btnRefreshTop) btnRefreshTop.addEventListener('click', onRefreshClick);

  ['ownerCardCaja', 'ownerCardInventario', 'ownerCardCredito', 'ownerCardCompras'].forEach(function (id) {
    var s = document.getElementById(id);
    if (s) bindSlot(s);
  });

  if (btnMic) {
    btnMic.addEventListener('click', function () {
      if (window.bootstrap && document.getElementById('ownerMicToast')) {
        new bootstrap.Toast(document.getElementById('ownerMicToast')).show();
      } else {
        alert('Voz Guardián: SD-2. No es despacho bodega.');
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

  fetchDashboard().then(function () {
    if (pollTimer) clearInterval(pollTimer);
    pollTimer = setInterval(fetchDashboard, Math.max(15000, pollMs));
  });
})();
