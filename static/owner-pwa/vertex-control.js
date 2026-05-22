/**
 * Centro de Mandos Global — LhexIA VERTEX (scope=global_maestro)
 */
(function () {
  'use strict';

  var root = document.getElementById('vertexControlApp');
  if (!root) return;

  var apiUrl = root.getAttribute('data-api-url') || '/api/v1/owner/dashboard?scope=global_maestro';
  var pollMs = parseInt(root.getAttribute('data-poll-ms') || '60000', 10);
  var pollTimer = null;

  var elGreeting = document.getElementById('vertexMaestroGreeting');
  var elLive = document.getElementById('vertexLiveStatus');
  var elResumen = document.getElementById('vertexResumenRed');
  var elGrid = document.getElementById('vertexClientGrid');
  var elFeed = document.getElementById('vertexFeedGlobal');
  var elMapSvg = document.getElementById('vertexAgentMapSvg');
  var elMapLegend = document.getElementById('vertexAgentMapLegend');
  var btnRefresh = document.getElementById('vertexBtnRefresh');

  var SEM_LABELS = { caja: 'Caja', inventario: 'Inv', credito: 'Créd', compras: 'OC' };
  var MODULO_LABELS = {
    vertex_guardian: 'Guardián',
    vertex_operador: 'Operador',
    vertex_logistica: 'Logística',
    vertex_inventario: 'Inventario',
  };

  function setLive(ok, text) {
    if (!elLive) return;
    var dot = elLive.querySelector('.vertex-live-dot');
    var txt = elLive.querySelector('.vertex-live-text');
    if (dot) dot.classList.toggle('err', !ok);
    if (txt) txt.textContent = text || (ok ? 'En vivo' : 'Error');
  }

  function esc(s) {
    var d = document.createElement('div');
    d.textContent = s == null ? '' : String(s);
    return d.innerHTML;
  }

  function renderResumen(resumen) {
    if (!elResumen || !resumen) return;
    var chips = [
      resumen.clientes_total + ' clientes',
      resumen.clientes_live + ' live · ' + resumen.clientes_mock + ' demo',
    ];
    if (resumen.eventos_red_neuronal != null) {
      chips.push(
        '<span class="vertex-chip">Red neuronal · ' +
          esc(String(resumen.eventos_red_neuronal)) +
          ' píldoras activas</span>'
      );
    }
    if (resumen.alertas_rojo > 0) {
      chips.push('<span class="vertex-chip vertex-chip--danger">' + resumen.alertas_rojo + ' crítico</span>');
    }
    if (resumen.alertas_amarillo > 0) {
      chips.push('<span class="vertex-chip vertex-chip--warn">' + resumen.alertas_amarillo + ' atención</span>');
    }
    if (resumen.ventas_hoy_red_live_fmt) {
      chips.push('<span class="vertex-chip">Live: ' + esc(resumen.ventas_hoy_red_live_fmt) + '</span>');
    }
    elResumen.innerHTML = chips
      .map(function (c, i) {
        if (c.indexOf('<span') === 0) return c;
        return '<span class="vertex-chip">' + esc(c) + '</span>';
      })
      .join('');
  }

  function renderClientes(clientes) {
    if (!elGrid) return;
    elGrid.innerHTML = '';
    (clientes || []).forEach(function (c) {
      var live = c.fuente_datos === 'live';
      var card = document.createElement('article');
      card.className =
        'vertex-client-card ' + (live ? 'vertex-client-card--live' : 'vertex-client-card--mock');
      var semHtml = '';
      var sem = c.semaforos || {};
      Object.keys(SEM_LABELS).forEach(function (k) {
        var est = (sem[k] || 'verde').toLowerCase();
        semHtml +=
          '<div class="vertex-sem vertex-sem--' +
          est +
          '"><div class="vertex-sem-dot"></div>' +
          esc(SEM_LABELS[k]) +
          '</div>';
      });
      var modHtml = (c.modulos_contratados || [])
        .map(function (m) {
          return (
            '<span class="vertex-modulo-pill">' +
            esc(MODULO_LABELS[m] || m) +
            '</span>'
          );
        })
        .join('');
      var kpis = c.kpis || {};
      card.innerHTML =
        '<div class="vertex-client-head">' +
        '<h3 class="vertex-client-name">' +
        esc(c.nombre) +
        '</h3>' +
        '<span class="vertex-client-badge vertex-client-badge--' +
        (live ? 'live' : 'mock') +
        '">' +
        (live ? 'LIVE' : 'DEMO') +
        '</span></div>' +
        '<div class="vertex-semaforos">' +
        semHtml +
        '</div>' +
        '<div class="vertex-modulos">' +
        modHtml +
        '</div>' +
        '<div class="vertex-client-kpi">Ventas hoy: <strong>' +
        esc(kpis.ventas_hoy_fmt || '$0') +
        '</strong></div>' +
        (c.pildoras_activas
          ? '<p class="vertex-client-msg"><span class="vertex-neural-tag">● red</span> ' +
            esc(String(c.pildoras_activas)) +
            ' píldora(s) activa(s)</p>'
          : '') +
        (c.mensaje_resumen
          ? '<p class="vertex-client-msg">' + esc(c.mensaje_resumen) + '</p>'
          : '');
      elGrid.appendChild(card);
    });
  }

  function renderFeed(items) {
    if (!elFeed) return;
    elFeed.innerHTML = '';
    if (!items || !items.length) {
      elFeed.innerHTML = '<li class="vertex-feed-item"><span class="vertex-feed-body">Sin eventos recientes.</span></li>';
      return;
    }
    items.forEach(function (it) {
      var li = document.createElement('li');
      li.className =
        'vertex-feed-item' + (it.severidad === 'critical' ? ' vertex-feed-item--critical' : '');
      li.innerHTML =
        '<span class="vertex-feed-client">' +
        esc((it.cliente_nombre || '').split(' ')[0]) +
        '</span>' +
        '<div class="vertex-feed-body">' +
        '<p class="vertex-feed-title">' +
        esc(it.titulo) +
        '</p>' +
        '<div class="vertex-feed-meta">' +
        esc(it.agente_producto || it.agente) +
        ' · v' +
        esc((it.pildora && it.pildora.vertex_pildora_version) || '1.0') +
        ' · ' +
        esc(it.hace) +
        (it.fuente_datos === 'mock' ? ' · demo' : ' · live') +
        (it.pildora && it.pildora.origen ? ' · ' + esc(it.pildora.origen) : '') +
        '</div></div>';
      elFeed.appendChild(li);
    });
  }

  function layoutNodes(nodos) {
    var byId = {};
    nodos.forEach(function (n) {
      byId[n.id] = n;
    });
    var hub = { x: 320, y: 40 };
    var clientes = nodos.filter(function (n) {
      return n.tipo === 'cliente';
    });
    var agents = nodos.filter(function (n) {
      return n.tipo === 'agente';
    });
    var positions = { vertex_hub: hub };
    var cw = 640;
    var n = Math.max(clientes.length, 1);
    clientes.forEach(function (c, i) {
      positions[c.id] = {
        x: (cw / (n + 1)) * (i + 1),
        y: 120,
      };
    });
    agents.forEach(function (a, i) {
      var parent = positions['cliente_' + a.cliente_id];
      if (!parent) parent = hub;
      positions[a.id] = {
        x: parent.x + ((i % 3) - 1) * 36,
        y: parent.y + 72,
      };
    });
    return positions;
  }

  function renderMap(grafo) {
    if (!elMapSvg || !grafo) return;
    var nodos = grafo.nodos || [];
    var aristas = grafo.aristas || [];
    var pos = layoutNodes(nodos);
    var stroke = { verde: '#34d399', amarillo: '#fbbf24', rojo: '#f43f5e', activo: '#818cf8', sync: '#6366f1' };

    var lines = aristas
      .map(function (e) {
        var p1 = pos[e.from];
        var p2 = pos[e.to];
        if (!p1 || !p2) return '';
        var col = stroke[e.estado] || stroke.sync;
        return (
          '<line x1="' +
          p1.x +
          '" y1="' +
          p1.y +
          '" x2="' +
          p2.x +
          '" y2="' +
          p2.y +
          '" stroke="' +
          col +
          '" stroke-width="1.5" stroke-opacity="0.55"/>'
        );
      })
      .join('');

    var circles = nodos
      .map(function (n) {
        var p = pos[n.id];
        if (!p) return '';
        var r = n.tipo === 'hub' ? 22 : n.tipo === 'cliente' ? 14 : 9;
        var fill =
          n.tipo === 'hub'
            ? '#6366f1'
            : n.tipo === 'cliente'
              ? n.estado_global === 'rojo'
                ? '#f43f5e'
                : n.estado_global === 'amarillo'
                  ? '#fbbf24'
                  : '#34d399'
              : '#818cf8';
        var label =
          n.tipo === 'hub'
            ? 'HUB'
            : (n.label || '').slice(0, 12);
        return (
          '<g><circle cx="' +
          p.x +
          '" cy="' +
          p.y +
          '" r="' +
          r +
          '" fill="' +
          fill +
          '" fill-opacity="0.85"/>' +
          '<text x="' +
          p.x +
          '" y="' +
          (p.y + r + 14) +
          '" text-anchor="middle" fill="#94a3b8" font-size="9" font-family="Inter,sans-serif">' +
          esc(label) +
          '</text></g>'
        );
      })
      .join('');

    elMapSvg.innerHTML = lines + circles;

    if (elMapLegend) {
      elMapLegend.innerHTML =
        '<span><span class="dot" style="background:#6366f1"></span> VERTEX Hub</span>' +
        '<span><span class="dot" style="background:#34d399"></span> Cliente OK</span>' +
        '<span><span class="dot" style="background:#818cf8"></span> Agente</span>';
    }
  }

  function applyData(data) {
    if (elGreeting && data.saludo) elGreeting.textContent = data.saludo;
    renderResumen(data.resumen_red);
    renderClientes(data.clientes);
    renderFeed(data.feed_preview_global);
    renderMap(data.grafo_agentes);
    setLive(true, 'Actualizado · ' + new Date().toLocaleTimeString('es-CL', { hour: '2-digit', minute: '2-digit' }));
  }

  function fetchDashboard() {
    setLive(true, 'Sincronizando…');
    return fetch(apiUrl, { credentials: 'same-origin', headers: { Accept: 'application/json' } })
      .then(function (r) {
        if (r.status === 401) {
          window.location.href = '/login?next=' + encodeURIComponent('/owner/vertex-control');
          throw new Error('login');
        }
        if (!r.ok) throw new Error('HTTP ' + r.status);
        return r.json();
      })
      .then(function (j) {
        if (j.status !== 'success' || !j.data) throw new Error('payload');
        if (j.data.scope !== 'global_maestro') throw new Error('scope');
        applyData(j.data);
      })
      .catch(function () {
        setLive(false, 'Sin conexión — reintente');
      });
  }

  function schedulePoll() {
    if (pollTimer) clearInterval(pollTimer);
    pollTimer = setInterval(fetchDashboard, pollMs);
  }

  if (btnRefresh) {
    btnRefresh.addEventListener('click', function () {
      fetchDashboard();
    });
  }

  fetchDashboard().then(schedulePoll);
})();
