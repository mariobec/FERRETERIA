/**
 * POS Retiros — vista premium + buscador inteligente (typeahead + filtro cola).
 */
(function () {
  'use strict';

  var cfgEl, modalEl, modal, ventaActual = null;
  var suggestTimer = null;
  var suggestIdx = -1;
  var lastSugerencias = [];

  function cfg() {
    if (!cfgEl) return {};
    return {
      buscarUrl: cfgEl.getAttribute('data-buscar-url') || '',
      sugerenciasUrl: cfgEl.getAttribute('data-sugerencias-url') || '',
      entregaTpl: cfgEl.getAttribute('data-entrega-url-template') || '',
    };
  }

  function entregaUrl(vid) {
    return cfg().entregaTpl.replace('/0/', '/' + String(vid) + '/');
  }

  function fmtMonto(n) {
    try {
      return Number(n || 0).toLocaleString('es-CL');
    } catch (e) {
      return String(n || 0);
    }
  }

  function $(id) {
    return document.getElementById(id);
  }

  function setEstadoBadge(el, data) {
    if (!el) return;
    var tipo = 'rojo';
    var label = 'Estado desconocido';
    if (data.transferencia_pendiente) {
      tipo = 'ambar';
      label = 'Transferencia sin confirmar en caja';
    } else if (data.solo_otro_canal) {
      tipo = 'ambar';
      label = data.mensaje || 'Se retira en bodega';
    } else if (data.entrega_completa) {
      tipo = 'gris';
      label = 'Entrega completada';
    } else if (data.pagado) {
      tipo = 'verde';
      label = 'Pagado — listo para entregar';
    } else if (data.estado_venta === 'Pendiente') {
      tipo = 'rojo';
      label = 'Pendiente de cobro en caja';
    } else {
      tipo = 'rojo';
      label = data.estado_venta || 'Estado desconocido';
    }
    el.className = 'retiros-semaforo-banner retiros-semaforo-banner--' + tipo + ' mb-3';
    el.innerHTML =
      '<div class="retiros-semaforo retiros-semaforo--' + tipo + '">' +
      '<div class="retiros-semaforo__lights" aria-hidden="true">' +
      '<span class="retiros-semaforo__dot retiros-semaforo__dot--rojo' + (tipo === 'rojo' ? ' is-active' : '') + '"></span>' +
      '<span class="retiros-semaforo__dot retiros-semaforo__dot--ambar' + (tipo === 'ambar' ? ' is-active' : '') + '"></span>' +
      '<span class="retiros-semaforo__dot retiros-semaforo__dot--verde' + (tipo === 'verde' ? ' is-active' : '') + '"></span>' +
      '</div>' +
      '<span class="retiros-semaforo-banner__text">' + label + '</span>' +
      '</div>';
  }

  function escapeHtml(s) {
    return String(s == null ? '' : s).replace(/[&<>"']/g, function (c) {
      return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c];
    });
  }

  function canalMeta(canal) {
    var ck = String(canal || 'Tienda').trim().toLowerCase();
    if (ck === 'bodega') return { cls: 'bodega', icon: 'fa-warehouse', label: 'Bodega' };
    if (ck === 'despacho') return { cls: 'despacho', icon: 'fa-truck', label: 'Despacho' };
    return { cls: 'tienda', icon: 'fa-store', label: 'Tienda' };
  }

  function renderModalLineas(lineas) {
    var cont = $('posRetiroModalLineasList');
    if (!cont) return;
    var arr = lineas || [];
    var pendientes = arr.filter(function (ln) { return Number(ln.pendiente || 0) > 0; });
    if (!pendientes.length) {
      cont.innerHTML = '<p class="retiros-lineas__empty text-muted small mb-0">No hay líneas pendientes de entrega en su canal.</p>';
      return;
    }
    cont.innerHTML = pendientes.map(function (ln) {
      var m = canalMeta(ln.canal);
      var pend = Number(ln.pendiente || 0);
      var ent = Number(ln.entregada || 0);
      var vend = Number(ln.cantidad || 0);
      return (
        '<div class="retiros-linea" data-detalle-id="' + ln.detalle_id + '" data-pendiente="' + pend + '">' +
        '<div class="retiros-linea__info">' +
        '<span class="retiros-canal-chip retiros-canal-chip--' + m.cls + '"><i class="fas ' + m.icon + ' me-1"></i>' + m.label + '</span>' +
        '<span class="retiros-linea__nombre">' + escapeHtml(ln.nombre) + '</span>' +
        '<span class="retiros-linea__meta">Vendido ' + vend + ' · Entregado ' + ent + ' · <strong>Pendiente ' + pend + '</strong></span>' +
        '</div>' +
        '<div class="retiros-linea__accion">' +
        '<input type="number" class="form-control form-control-sm retiros-linea__cant" min="1" max="' + pend + '" value="' + pend + '" aria-label="Cantidad a entregar">' +
        '<button type="button" class="btn btn-sm btn-success retiros-linea__btn" data-detalle-id="' + ln.detalle_id + '">' +
        '<i class="fas fa-check me-1"></i>Entregar</button>' +
        '</div>' +
        '</div>'
      );
    }).join('');
    cont.querySelectorAll('.retiros-linea__btn').forEach(function (btn) {
      btn.addEventListener('click', function () {
        var wrap = btn.closest('.retiros-linea');
        if (!wrap) return;
        var did = parseInt(btn.getAttribute('data-detalle-id'), 10);
        var inp = wrap.querySelector('.retiros-linea__cant');
        var cant = parseInt(inp && inp.value, 10);
        var pend = parseInt(wrap.getAttribute('data-pendiente'), 10);
        if (!cant || cant < 1) { alert('Cantidad inválida.'); return; }
        if (cant > pend) { alert('La cantidad supera lo pendiente (' + pend + ').'); return; }
        entregarLinea(ventaActual && ventaActual.venta_id, did, cant);
      });
    });
  }

  function mostrarModal(data) {
    ventaActual = data;
    var folio = data.folio || ('VL' + String(data.venta_id || '').padStart(6, '0'));
    var elFolio = $('posRetiroModalFolio');
    if (elFolio) elFolio.textContent = folio;
    var elVid = $('posRetiroModalValeId');
    if (elVid) elVid.textContent = data.venta_id;
    var elCli = $('posRetiroModalCliente');
    if (elCli) elCli.textContent = data.cliente || '—';
    var elMon = $('posRetiroModalMonto');
    if (elMon) elMon.textContent = fmtMonto(data.monto);
    var elLin = $('posRetiroModalLineas');
    if (elLin) elLin.textContent = String(data.lineas_pendientes != null ? data.lineas_pendientes : '—');
    var elMsg = $('posRetiroModalMsg');
    if (elMsg) elMsg.textContent = data.mensaje || '';
    setEstadoBadge($('posRetiroModalEstado'), data);
    renderModalLineas(data.lineas);
    var btn = $('posRetiroBtnEntregar');
    if (btn) btn.disabled = !data.puede_entregar;
    if (modal) modal.show();
  }

  function aplicarResultadoEntrega(vid, data) {
    // Refresca modal y fila de cola tras una entrega (parcial o total).
    if (ventaActual && ventaActual.venta_id === vid) {
      ventaActual.lineas = data.lineas || [];
      var pend = (data.lineas || []).filter(function (ln) { return Number(ln.pendiente || 0) > 0; }).length;
      ventaActual.lineas_pendientes = pend;
      ventaActual.entrega_completa = !!data.completa;
      ventaActual.puede_entregar = pend > 0 && !ventaActual.transferencia_pendiente;
      var elLin = $('posRetiroModalLineas');
      if (elLin) elLin.textContent = String(pend);
      renderModalLineas(data.lineas);
      setEstadoBadge($('posRetiroModalEstado'), ventaActual);
      var btnAll = $('posRetiroBtnEntregar');
      if (btnAll) btnAll.disabled = !ventaActual.puede_entregar;
    }
    actualizarFilaCola(vid, data);
    if (data.completa) {
      if (modal) modal.hide();
    }
  }

  function actualizarFilaCola(vid, data) {
    var row = document.querySelector('.pos-retiros-row[data-venta-id="' + vid + '"]');
    if (!row) return;
    if (data.completa) {
      row.remove();
      actualizarContadores();
      if (!document.querySelectorAll('.pos-retiros-row').length) window.location.reload();
      return;
    }
    // Entrega parcial: actualizar contador de pendientes de la fila.
    var pend = (data.lineas || []).filter(function (ln) { return Number(ln.pendiente || 0) > 0; }).length;
    var badge = row.querySelector('.retiros-badge--count');
    if (badge) badge.textContent = String(pend);
    row.classList.add('is-highlight');
  }

  async function buscarExacto(q) {
    var c = cfg();
    if (!c.buscarUrl || !q) return null;
    var r = await fetch(c.buscarUrl + '?q=' + encodeURIComponent(q), {
      credentials: 'same-origin',
      headers: { Accept: 'application/json' },
    });
    return r.json().catch(function () {
      return { ok: false, mensaje: 'Error de red.' };
    });
  }

  async function abrirBusqueda(q) {
    var qq = (q || '').trim();
    if (!qq) return;
    ocultarSugerencias();
    var data = await buscarExacto(qq);
    if (!data || !data.ok) {
      alert((data && data.mensaje) || 'No se encontró el ticket.');
      return;
    }
    data.folio = data.folio || ('VL' + String(data.venta_id).padStart(6, '0'));
    mostrarModal(data);
  }

  function normalizarQ(q) {
    return (q || '').trim().toLowerCase();
  }

  function filtrarTablaLocal(q) {
    var nq = normalizarQ(q);
    var rows = document.querySelectorAll('.pos-retiros-row');
    var visible = 0;
    rows.forEach(function (tr) {
      var blob = (tr.getAttribute('data-search') || '').toLowerCase();
      var show = !nq || blob.indexOf(nq) >= 0 || nq.split(/\s+/).every(function (t) {
        return !t || blob.indexOf(t) >= 0;
      });
      tr.classList.toggle('is-hidden', !show);
      tr.classList.toggle('is-highlight', false);
      if (show) visible += 1;
    });
    var noMatch = $('retirosNoMatch');
    if (noMatch) noMatch.classList.toggle('d-none', !nq || visible > 0 || !rows.length);
    var hint = $('retirosFilterHint');
    if (hint && nq) {
      hint.textContent = visible
        ? 'Mostrando ' + visible + ' vale(s) que coinciden con «' + q.trim() + '».'
        : 'Ningún vale en cola coincide con «' + q.trim() + '».';
    }
    return visible;
  }

  function ocultarSugerencias() {
    var list = $('retirosSuggestList');
    if (list) {
      list.classList.add('d-none');
      list.innerHTML = '';
    }
    var inp = $('retirosSmartSearch');
    if (inp) inp.setAttribute('aria-expanded', 'false');
    suggestIdx = -1;
    lastSugerencias = [];
  }

  function renderSugerencias(items) {
    var list = $('retirosSuggestList');
    var inp = $('retirosSmartSearch');
    if (!list) return;
    lastSugerencias = items || [];
    suggestIdx = -1;
    if (!items || !items.length) {
      list.classList.add('d-none');
      list.innerHTML = '';
      if (inp) inp.setAttribute('aria-expanded', 'false');
      return;
    }
    list.innerHTML = items.map(function (it, i) {
      return (
        '<li class="retiros-suggest-item" role="option" data-idx="' + i + '" data-vid="' + it.venta_id + '">' +
        '<div class="retiros-suggest-item__main">' +
        '<div class="retiros-suggest-item__folio">' + (it.folio || '') + '</div>' +
        '<div class="retiros-suggest-item__cliente">' + (it.cliente || '—') + '</div>' +
        '</div>' +
        '<div class="retiros-suggest-item__meta">' +
        '$' + fmtMonto(it.monto) + '<br>' + (it.lineas_pendientes || 0) + ' línea(s)' +
        '</div></li>'
      );
    }).join('');
    list.classList.remove('d-none');
    if (inp) inp.setAttribute('aria-expanded', 'true');
    list.querySelectorAll('.retiros-suggest-item').forEach(function (el) {
      el.addEventListener('mousedown', function (ev) {
        ev.preventDefault();
        var idx = parseInt(el.getAttribute('data-idx'), 10);
        seleccionarSugerencia(idx);
      });
    });
  }

  function marcarSugerenciaActiva() {
    var list = $('retirosSuggestList');
    if (!list) return;
    list.querySelectorAll('.retiros-suggest-item').forEach(function (el, i) {
      el.classList.toggle('is-active', i === suggestIdx);
    });
  }

  function seleccionarSugerencia(idx) {
    var it = lastSugerencias[idx];
    if (!it) return;
    var inp = $('retirosSmartSearch');
    if (inp) inp.value = it.folio || String(it.venta_id);
    ocultarSugerencias();
    filtrarTablaLocal(inp ? inp.value : '');
    resaltarFila(it.venta_id);
    abrirBusqueda(it.folio || ('VL' + String(it.venta_id).padStart(6, '0')));
  }

  function resaltarFila(vid) {
    document.querySelectorAll('.pos-retiros-row').forEach(function (tr) {
      var match = parseInt(tr.getAttribute('data-venta-id'), 10) === parseInt(vid, 10);
      tr.classList.toggle('is-highlight', match);
      if (match) tr.scrollIntoView({ block: 'nearest', behavior: 'smooth' });
    });
  }

  async function cargarSugerencias(q) {
    var c = cfg();
    if (!c.sugerenciasUrl || (q || '').trim().length < 2) {
      ocultarSugerencias();
      return;
    }
    var r = await fetch(c.sugerenciasUrl + '?q=' + encodeURIComponent(q.trim()), {
      credentials: 'same-origin',
      headers: { Accept: 'application/json' },
    });
    var data = await r.json().catch(function () {
      return { ok: false, sugerencias: [] };
    });
    if (data.ok) renderSugerencias(data.sugerencias || []);
  }

  function programarSugerencias(q) {
    clearTimeout(suggestTimer);
    suggestTimer = setTimeout(function () {
      cargarSugerencias(q);
    }, 220);
  }

  function actualizarContadores() {
    var rows = document.querySelectorAll('.pos-retiros-row');
    var n = rows.length;
    ['retirosStatCola', 'retirosKpiCola'].forEach(function (id) {
      var el = $(id);
      if (el) el.textContent = String(n);
    });
  }

  async function entregarTodo(vid) {
    if (!vid) return;
    if (!confirm('¿Entregar todo lo pendiente de su canal del vale #' + vid + '?')) return;
    var r = await fetch(entregaUrl(vid), {
      method: 'POST',
      credentials: 'same-origin',
      headers: { 'Content-Type': 'application/json', Accept: 'application/json' },
      body: JSON.stringify({ accion: 'entregar_todo' }),
    });
    var data = await r.json().catch(function () {
      return { ok: false, mensaje: 'Error de red.' };
    });
    if (data.ok) {
      aplicarResultadoEntrega(vid, data);
    } else {
      alert(data.mensaje || 'No se pudo registrar la entrega.');
    }
  }

  async function entregarLinea(vid, detalleId, cantidad) {
    if (!vid || !detalleId || !cantidad) return;
    var r = await fetch(entregaUrl(vid), {
      method: 'POST',
      credentials: 'same-origin',
      headers: { 'Content-Type': 'application/json', Accept: 'application/json' },
      body: JSON.stringify({ accion: 'entregar_linea', detalle_id: detalleId, cantidad: cantidad }),
    });
    var data = await r.json().catch(function () {
      return { ok: false, mensaje: 'Error de red.' };
    });
    if (data.ok) {
      aplicarResultadoEntrega(vid, data);
    } else {
      alert(data.mensaje || 'No se pudo registrar la entrega de la línea.');
    }
  }

  function toggleClearBtn(q) {
    var btn = $('retirosSearchClear');
    if (btn) btn.classList.toggle('d-none', !(q || '').trim());
  }

  document.addEventListener('DOMContentLoaded', function () {
    cfgEl = $('posRetirosConfig');
    modalEl = $('modalPosRetiroScan');
    if (modalEl && typeof bootstrap !== 'undefined') {
      modal = bootstrap.Modal.getOrCreateInstance(modalEl);
    }

    var smart = $('retirosSmartSearch');
    var clearBtn = $('retirosSearchClear');
    var wedge = $('posRetirosWedge');

    if (smart) {
      smart.addEventListener('input', function () {
        var q = smart.value;
        toggleClearBtn(q);
        filtrarTablaLocal(q);
        programarSugerencias(q);
      });
      smart.addEventListener('keydown', function (ev) {
        if (ev.key === 'ArrowDown' && lastSugerencias.length) {
          ev.preventDefault();
          suggestIdx = Math.min(suggestIdx + 1, lastSugerencias.length - 1);
          marcarSugerenciaActiva();
          return;
        }
        if (ev.key === 'ArrowUp' && lastSugerencias.length) {
          ev.preventDefault();
          suggestIdx = Math.max(suggestIdx - 1, 0);
          marcarSugerenciaActiva();
          return;
        }
        if (ev.key === 'Enter') {
          ev.preventDefault();
          if (suggestIdx >= 0 && lastSugerencias[suggestIdx]) {
            seleccionarSugerencia(suggestIdx);
          } else {
            abrirBusqueda(smart.value);
          }
          return;
        }
        if (ev.key === 'Escape') {
          ocultarSugerencias();
        }
      });
      smart.addEventListener('blur', function () {
        setTimeout(ocultarSugerencias, 180);
      });
    }

    if (clearBtn && smart) {
      clearBtn.addEventListener('click', function () {
        smart.value = '';
        toggleClearBtn('');
        filtrarTablaLocal('');
        ocultarSugerencias();
        var hint = $('retirosFilterHint');
        if (hint) {
          var n = document.querySelectorAll('.pos-retiros-row').length;
          hint.textContent = 'Mostrando ' + n + ' vale(s) pagado(s) con mercadería pendiente.';
        }
        smart.focus();
      });
    }

    if (wedge) {
      wedge.addEventListener('keydown', function (ev) {
        if (ev.key !== 'Enter') return;
        ev.preventDefault();
        var q = (wedge.value || '').trim();
        wedge.value = '';
        if (q) abrirBusqueda(q);
      });
    }

    document.querySelectorAll('.retiros-btn-entregar').forEach(function (btn) {
      btn.addEventListener('click', function () {
        var vid = parseInt(btn.getAttribute('data-venta-id'), 10);
        if (!vid) return;
        abrirBusqueda('VL' + String(vid).padStart(6, '0'));
      });
    });

    var btnEntregar = $('posRetiroBtnEntregar');
    if (btnEntregar) {
      btnEntregar.addEventListener('click', function () {
        if (ventaActual && ventaActual.venta_id) {
          entregarTodo(ventaActual.venta_id);
        }
      });
    }
  });
})();
