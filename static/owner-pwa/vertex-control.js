/**
 * Centro de Mandos Global — LhexIA VERTEX (red neuronal cognitiva)
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
  var elNeuralSvg = document.getElementById('vertexNeuralSvg');
  var elMapLegend = document.getElementById('vertexAgentMapLegend');
  var elHud = document.getElementById('vertexNeuralHud');
  var elRailLeft = document.getElementById('vertexAgentRailLeft');
  var elRailRight = document.getElementById('vertexAgentRailRight');
  var btnRefresh = document.getElementById('vertexBtnRefresh');

  var HUB = { x: 400, y: 262 };
  var CLIENT_SLOTS = [
    { x: 128, y: 118 },
    { x: 672, y: 118 },
    { x: 672, y: 402 },
  ];

  var SEM_LABELS = { caja: 'Caja', inventario: 'Inv', credito: 'Créd', compras: 'OC' };
  var MODULO_LABELS = {
    vertex_guardian: 'Guardián',
    vertex_operador: 'Operador',
    vertex_logistica: 'Logística',
    vertex_inventario: 'Inventario',
  };

  var SVG_DEFS =
    '<defs>' +
    '<filter id="vc-glow-cyan" x="-50%" y="-50%" width="200%" height="200%">' +
    '<feGaussianBlur stdDeviation="3" result="b"/>' +
    '<feMerge><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge>' +
    '</filter>' +
    '<filter id="vc-glow-red" x="-50%" y="-50%" width="200%" height="200%">' +
    '<feGaussianBlur stdDeviation="4" result="b"/>' +
    '<feMerge><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge>' +
    '</filter>' +
    '<linearGradient id="vc-trace-cyan" x1="0%" y1="0%" x2="100%" y2="0%">' +
    '<stop offset="0%" stop-color="#22d3ee" stop-opacity="0.2"/>' +
    '<stop offset="50%" stop-color="#67e8f9" stop-opacity="1"/>' +
    '<stop offset="100%" stop-color="#22d3ee" stop-opacity="0.2"/>' +
    '</linearGradient>' +
    '<linearGradient id="vc-trace-red" x1="0%" y1="0%" x2="100%" y2="0%">' +
    '<stop offset="0%" stop-color="#fb7185" stop-opacity="0.3"/>' +
    '<stop offset="50%" stop-color="#ff3366" stop-opacity="1"/>' +
    '<stop offset="100%" stop-color="#fb7185" stop-opacity="0.3"/>' +
    '</linearGradient>' +
    '</defs>';

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

  function estadoCircuit(estado) {
    var e = (estado || 'verde').toLowerCase();
    return e === 'rojo' ? 'critical' : e === 'amarillo' ? 'warn' : 'ok';
  }

  function pcbPath(x1, y1, x2, y2, offset) {
    var off = offset || 0;
    var mx = x1 + (x2 - x1) * 0.42;
    return (
      'M' + (x1 + off) + ' ' + (y1 + off * 0.5) +
      ' L' + (mx + off) + ' ' + (y1 + off * 0.5) +
      ' L' + (mx + off) + ' ' + (y2 - off * 0.5) +
      ' L' + (x2 + off) + ' ' + (y2 - off * 0.5)
    );
  }

  function energyDuration(circuit) {
    if (circuit === 'critical') return { main: 1.05, sec: 1.35 };
    if (circuit === 'warn') return { main: 1.6, sec: 2 };
    return { main: 2.2, sec: 2.8 };
  }

  function layoutNeural(grafo, clientes) {
    var pos = { vertex_hub: HUB };
    var list = clientes && clientes.length ? clientes : [];
    list.forEach(function (c, i) {
      var slot = CLIENT_SLOTS[i] || CLIENT_SLOTS[CLIENT_SLOTS.length - 1];
      var cid = c.id;
      pos['cliente_' + cid] = {
        x: slot.x,
        y: slot.y,
        estado: c.estado_global || 'verde',
        label: c.nombre || cid,
      };
      var agents = c.agentes_activos || [];
      agents.forEach(function (ag, j) {
        var nid = cid + '_' + ag;
        pos[nid] = {
          x: slot.x + (j - (agents.length - 1) / 2) * 48,
          y: slot.y + 52,
          label: ag,
          tipo: 'agente',
        };
      });
    });
    (grafo.nodos || []).forEach(function (n) {
      if (pos[n.id]) return;
      if (n.tipo === 'agente' && n.cliente_id) {
        var parent = pos['cliente_' + n.cliente_id];
        if (parent) {
          var siblings = (grafo.nodos || []).filter(function (x) {
            return x.tipo === 'agente' && x.cliente_id === n.cliente_id;
          });
          var idx = siblings.findIndex(function (x) { return x.id === n.id; });
          pos[n.id] = {
            x: parent.x + (idx - (siblings.length - 1) / 2) * 48,
            y: parent.y + 52,
            label: n.label || n.id,
            tipo: 'agente',
          };
        }
      }
    });
    return pos;
  }

  var SVG_NS = 'http://www.w3.org/2000/svg';
  var circuitLoops = [];

  function circuitKind(el) {
    if (el.classList.contains('vertex-circuit-energy--critical')) return 'critical';
    if (el.classList.contains('vertex-circuit-energy--warn')) return 'warn';
    return 'ok';
  }

  function cancelCircuitMotion() {
    circuitLoops.forEach(function (l) {
      if (l && l.cancel) l.cancel();
    });
    circuitLoops = [];
  }

  function attachTravelDot(pathEl, circuit, seconds) {
    var len = Math.max(40, pathEl.getTotalLength() || 0);
    if (!len) return;
    var dot = document.createElementNS(SVG_NS, 'circle');
    dot.setAttribute('class', 'vertex-circuit-dot vertex-circuit-dot--' + circuit);
    dot.setAttribute('r', circuit === 'critical' ? '5' : '4');
    pathEl.parentNode.appendChild(dot);
    var t0 = performance.now();
    var stopped = false;
    function tick(now) {
      if (stopped) return;
      var t = ((now - t0) / (seconds * 1000)) % 1;
      var pt = pathEl.getPointAtLength(t * len);
      dot.setAttribute('cx', String(pt.x));
      dot.setAttribute('cy', String(pt.y));
      requestAnimationFrame(tick);
    }
    requestAnimationFrame(tick);
    circuitLoops.push({
      cancel: function () {
        stopped = true;
        if (dot.parentNode) dot.parentNode.removeChild(dot);
      },
    });
  }

  function wireEnergyPaths() {
    if (!elNeuralSvg) return;
    elNeuralSvg.classList.add('vertex-neural-live');
    elNeuralSvg.querySelectorAll('.vertex-circuit-energy').forEach(function (p) {
      p.classList.add('vertex-dash-anim');
      if (!p.classList.contains('vertex-circuit-energy--secondary')) {
        attachTravelDot(p, circuitKind(p), energyDuration(circuitKind(p)).main);
      }
    });
    elNeuralSvg.querySelectorAll('.vertex-circuit-track').forEach(function (p) {
      p.classList.add('vertex-circuit-flow-anim', 'vertex-dash-anim-track');
      if (p.classList.contains('vertex-circuit-track--critical')) {
        p.classList.add('vertex-circuit-flow-anim--critical');
      } else if (p.classList.contains('vertex-circuit-track--warn')) {
        p.classList.add('vertex-circuit-flow-anim--warn');
      } else {
        p.classList.add('vertex-circuit-flow-anim--ok');
      }
    });
  }

  function scheduleWireEnergy() {
    requestAnimationFrame(wireEnergyPaths);
  }

  function renderNeuralSvg(grafo, clientes) {
    if (!elNeuralSvg || !grafo) return;
    var pos = layoutNeural(grafo, clientes);
    var aristas = grafo.aristas || [];
    var nodos = grafo.nodos || [];
    var traces = '';
    var nodes = '';
    var agents = '';
    var hub = pos.vertex_hub || HUB;

    traces +=
      '<g class="vertex-hub-svg">' +
      '<circle class="vertex-hub-port" cx="' + hub.x + '" cy="' + hub.y + '" r="8"/>' +
      '</g>';

    aristas.forEach(function (e) {
      if (e.tipo !== 'tenant') return;
      var p1 = pos[e.from];
      var p2 = pos[e.to];
      if (!p1 || !p2) return;
      var circuit = estadoCircuit(e.estado || p2.estado);
      var dur = energyDuration(circuit);
      var filter = circuit === 'critical' ? 'vc-glow-red' : 'vc-glow-cyan';
      var grad = circuit === 'critical' ? 'vc-trace-red' : 'vc-trace-cyan';
      var offsets = [-4, 0, 4];

      offsets.forEach(function (off, idx) {
        var pathD = pcbPath(p1.x, p1.y, p2.x, p2.y, off);
        if (idx === 0) {
          traces +=
            '<path class="vertex-circuit-rail vertex-circuit-rail--' + circuit + '" d="' + pathD + '" stroke-width="8"/>';
        }
        if (idx === 1) {
          traces +=
            '<path class="vertex-circuit-track vertex-circuit-track--' + circuit + '" d="' + pathD + '" stroke-width="2" filter="url(#' + filter + ')"/>' +
            '<path class="vertex-circuit-energy vertex-circuit-energy--' + circuit + '" d="' + pathD + '"/>';
        } else {
          traces +=
            '<path class="vertex-circuit-energy vertex-circuit-energy--' + circuit + ' vertex-circuit-energy--secondary" d="' + pathD + '"/>';
        }
      });
    });

    nodos.forEach(function (n) {
      if (n.tipo === 'hub') return;
      var p = pos[n.id];
      if (!p) return;
      if (n.tipo === 'cliente') {
        var st = estadoCircuit(n.estado_global);
        var r = 20;
        nodes +=
          '<g class="vertex-node vertex-node--client vertex-node--' + st + '" data-id="' + esc(n.id) + '">' +
          '<circle cx="' + p.x + '" cy="' + p.y + '" r="' + (r + 8) + '" class="vertex-node-halo"/>' +
          '<circle cx="' + p.x + '" cy="' + p.y + '" r="' + r + '" class="vertex-node-core"/>' +
          '<text x="' + p.x + '" y="' + (p.y + r + 16) + '" text-anchor="middle" class="vertex-node-label">' + esc((n.label || '').slice(0, 16)) + '</text>' +
          '</g>';
      }
    });

    nodos.forEach(function (n) {
      if (n.tipo !== 'agente') return;
      var p = pos[n.id];
      if (!p) return;
      agents +=
        '<g class="vertex-node vertex-node--agent">' +
        '<circle cx="' + p.x + '" cy="' + p.y + '" r="11" class="vertex-node-agent-core"/>' +
        '<text x="' + p.x + '" y="' + (p.y + 22) + '" text-anchor="middle" class="vertex-node-agent-label">' + esc((n.label || '').slice(0, 11)) + '</text>' +
        '</g>';
    });

    aristas.forEach(function (e) {
      if (e.tipo !== 'contrato') return;
      var p1 = pos[e.from];
      var p2 = pos[e.to];
      if (!p1 || !p2) return;
      traces +=
        '<line x1="' + p1.x + '" y1="' + p1.y + '" x2="' + p2.x + '" y2="' + p2.y + '" class="vertex-link-agent" stroke-width="1"/>';
    });

    cancelCircuitMotion();
    elNeuralSvg.innerHTML = SVG_DEFS + '<g class="vertex-circuits">' + traces + '</g>' + nodes + agents;
    scheduleWireEnergy();

    if (elMapLegend) {
      elMapLegend.innerHTML =
        '<span><span class="dot dot--cyan"></span> Circuito activo</span>' +
        '<span><span class="dot dot--red"></span> Crítico · pulsos rápidos</span>' +
        '<span><span class="dot dot--amber"></span> Atención</span>' +
        '<span><span class="dot dot--agent"></span> Agente</span>';
    }
  }

  function autonomyPct(resumen) {
    if (!resumen) return 85;
    var drop = (resumen.alertas_rojo || 0) * 14 + (resumen.alertas_amarillo || 0) * 5;
    return Math.max(42, Math.min(98, 92 - drop));
  }

  function renderHud(resumen) {
    if (!elHud) return;
    var pct = autonomyPct(resumen);
    var crit = (resumen && resumen.alertas_rojo) || 0;
    elHud.innerHTML =
      '<div class="vertex-hud-card vertex-hud-card--glass">' +
      '<div class="vertex-hud-ring" style="--pct:' + pct + '">' +
      '<svg viewBox="0 0 36 36" aria-hidden="true"><circle class="vertex-hud-ring-bg" cx="18" cy="18" r="15.5"/>' +
      '<circle class="vertex-hud-ring-fg" cx="18" cy="18" r="15.5" stroke-dasharray="' + pct + ', 100"/></svg>' +
      '<span class="vertex-hud-ring-val">' + pct + '%</span></div>' +
      '<div><div class="vertex-hud-label">Autonomía agentes</div>' +
      '<div class="vertex-hud-sub">' + crit + ' crítico · red maestra</div></div></div>' +
      '<div class="vertex-hud-card vertex-hud-card--glass vertex-hud-card--status">' +
      '<i class="fas fa-plug-circle-check"></i> LhexIA Connect <strong>Fase 3</strong></div>';
  }

  function previewCard(item, side) {
    var sev = (item.severidad || 'info').toLowerCase();
    var border = sev === 'critical' ? 'critical' : sev === 'warning' ? 'warn' : 'info';
    var icon =
      sev === 'critical'
        ? 'fa-triangle-exclamation'
        : sev === 'warning'
          ? 'fa-circle-exclamation'
          : 'fa-robot';
    var agentLabel = MODULO_LABELS[item.agente_producto] || item.agente || 'Agente';
    var href = item.nav_href || '#';
    return (
      '<article class="vertex-glass-card vertex-glass-card--' + border + '">' +
      '<header class="vertex-glass-card__head">' +
      '<span class="vertex-glass-card__icon"><i class="fas ' + icon + '"></i></span>' +
      '<span class="vertex-glass-card__agent">Agente Preview — ' + esc(agentLabel) + '</span>' +
      '</header>' +
      '<p class="vertex-glass-card__body">' + esc(item.titulo || '') + '</p>' +
      '<footer class="vertex-glass-card__foot">' +
      '<span class="vertex-glass-card__meta">' + esc(item.cliente_nombre || '') + ' · ' + esc(item.hace || '') + '</span>' +
      '<a href="' + esc(href) + '" class="vertex-glass-card__cta">Revisar detalle</a>' +
      '</footer></article>'
    );
  }

  function pickPreviews(feed) {
    var left = [];
    var right = [];
    (feed || []).forEach(function (it) {
      var ag = String(it.agente_producto || it.agente || '').toLowerCase();
      if (ag.indexOf('guardian') >= 0 || ag.indexOf('guardi') >= 0) {
        left.push(it);
      } else {
        right.push(it);
      }
    });
    var rank = { critical: 0, warning: 1, info: 2 };
    function sortFeed(a, b) {
      return (rank[a.severidad] || 9) - (rank[b.severidad] || 9);
    }
    left.sort(sortFeed);
    right.sort(sortFeed);
    return { left: left.slice(0, 2), right: right.slice(0, 2) };
  }

  function renderAgentRails(feed) {
    var rails = pickPreviews(feed);
    if (elRailLeft) {
      elRailLeft.innerHTML = rails.left.length
        ? rails.left.map(function (it) { return previewCard(it, 'left'); }).join('')
        : '<p class="vertex-rail-empty">Sin alertas Guardián</p>';
    }
    if (elRailRight) {
      elRailRight.innerHTML = rails.right.length
        ? rails.right.map(function (it) { return previewCard(it, 'right'); }).join('')
        : '<p class="vertex-rail-empty">Sin eventos logística</p>';
    }
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
      .map(function (c) {
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
          return '<span class="vertex-modulo-pill">' + esc(MODULO_LABELS[m] || m) + '</span>';
        })
        .join('');
      var kpis = c.kpis || {};
      card.innerHTML =
        '<div class="vertex-client-head">' +
        '<h3 class="vertex-client-name">' + esc(c.nombre) + '</h3>' +
        '<span class="vertex-client-badge vertex-client-badge--' + (live ? 'live' : 'mock') + '">' +
        (live ? 'LIVE' : 'DEMO') + '</span></div>' +
        '<div class="vertex-semaforos">' + semHtml + '</div>' +
        '<div class="vertex-modulos">' + modHtml + '</div>' +
        '<div class="vertex-client-kpi">Ventas hoy: <strong>' + esc(kpis.ventas_hoy_fmt || '$0') + '</strong></div>' +
        (c.pildoras_activas
          ? '<p class="vertex-client-msg"><span class="vertex-neural-tag">● red</span> ' + esc(String(c.pildoras_activas)) + ' píldora(s)</p>'
          : '') +
        (c.mensaje_resumen ? '<p class="vertex-client-msg">' + esc(c.mensaje_resumen) + '</p>' : '');
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
      li.className = 'vertex-feed-item' + (it.severidad === 'critical' ? ' vertex-feed-item--critical' : '');
      li.innerHTML =
        '<span class="vertex-feed-client">' + esc((it.cliente_nombre || '').split(' ')[0]) + '</span>' +
        '<div class="vertex-feed-body">' +
        '<p class="vertex-feed-title">' + esc(it.titulo) + '</p>' +
        '<div class="vertex-feed-meta">' + esc(it.agente_producto || it.agente) + ' · ' + esc(it.hace) +
        (it.fuente_datos === 'mock' ? ' · demo' : ' · live') + '</div></div>';
      elFeed.appendChild(li);
    });
  }

  function applyData(data) {
    if (elGreeting && data.saludo) elGreeting.textContent = data.saludo;
    renderResumen(data.resumen_red);
    renderHud(data.resumen_red);
    renderClientes(data.clientes);
    renderFeed(data.feed_preview_global);
    renderNeuralSvg(data.grafo_agentes, data.clientes);
    renderAgentRails(data.feed_preview_global);
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

  if (btnRefresh) btnRefresh.addEventListener('click', fetchDashboard);

  fetchDashboard().then(function () {
    if (pollTimer) clearInterval(pollTimer);
    pollTimer = setInterval(fetchDashboard, pollMs);
  });
})();
