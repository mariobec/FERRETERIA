(function () {
  'use strict';

  var root = document.getElementById('pv2App');
  if (!root) return;

  var URLS = {
    registrar: root.getAttribute('data-url-registrar'),
    buscar: root.getAttribute('data-url-buscar'),
    venta: root.getAttribute('data-url-venta'),
    producto: root.getAttribute('data-url-producto'),
    ticket: root.getAttribute('data-url-ticket')
  };

  var state = {
    step: 1,
    tipo: null, // devolucion | cambio | sin_comprobante
    venta: null,
    clienteId: null,
    saldoFavor: 0,
    // items from sale (selectable)
    saleLines: [],
    // {codigo, nombre, cantidad, max, precio, fromVenta}
    devueltos: [],
    entregados: []
  };

  function $(id) { return document.getElementById(id); }
  function money(n) {
    var v = Math.round(Number(n) || 0);
    return '$' + v.toLocaleString('es-CL');
  }
  function tot(arr) {
    return arr.reduce(function (s, r) {
      return s + (Number(r.precio) || 0) * (Number(r.cantidad) || 0);
    }, 0);
  }
  function rowLine(r) {
    return r.codigo + ',' + r.cantidad + ',' + Math.round(Number(r.precio) || 0);
  }

  function showMsg(el, text, isErr) {
    if (!el) return;
    if (!text) { el.hidden = true; el.textContent = ''; return; }
    el.hidden = false;
    el.textContent = text;
    el.classList.toggle('err', !!isErr);
  }

  function goStep(n) {
    if (state.tipo === 'devolucion' && n === 4) n = 5;
    if (state.tipo === 'devolucion' && state.step === 5 && n === 4) n = 3;
    state.step = n;
    document.querySelectorAll('.pv2-panel').forEach(function (p) {
      p.classList.toggle('is-active', Number(p.getAttribute('data-panel')) === n);
    });
    document.querySelectorAll('.pv2-step').forEach(function (b) {
      var s = Number(b.getAttribute('data-step'));
      b.classList.toggle('is-active', s === n);
      b.classList.toggle('is-done', s < n);
      if (state.tipo === 'devolucion' && s === 4) b.style.display = 'none';
      else b.style.display = '';
    });
    if (n === 4) renderEnt();
    if (n === 5) renderConfirm();
    updateDock();
    var dock = $('pv2Dock');
    if (dock) dock.hidden = n < 3;
  }

  function updateDock() {
    var d = tot(state.devueltos);
    var e = tot(state.entregados);
    var saldoUsado = 0;
    var neto = e - d - saldoUsado;
    $('pv2DockDev').textContent = money(d);
    $('pv2DockEnt').textContent = money(e);
    var entRow = $('pv2DockEntRow');
    if (entRow) entRow.style.display = state.tipo === 'devolucion' ? 'none' : '';
    var acc = $('pv2DockAccion');
    var netoEl = $('pv2DockNeto');
    if (neto > 0) {
      acc.textContent = 'Paga';
      netoEl.textContent = money(neto);
    } else if (neto < 0) {
      acc.textContent = 'A favor';
      netoEl.textContent = money(Math.abs(neto));
    } else {
      acc.textContent = 'Compensado';
      netoEl.textContent = '$0';
    }
    var go4 = $('pv2Go4');
    if (go4) go4.disabled = state.devueltos.length === 0;
  }

  function syncDevFromSaleChecks() {
    state.devueltos = state.devueltos.filter(function (r) { return !r.fromVenta; });
    state.saleLines.forEach(function (line) {
      if (!line.selected || line.cantidad <= 0) return;
      state.devueltos.push({
        codigo: line.codigo,
        nombre: line.nombre,
        cantidad: line.cantidad,
        max: line.max,
        precio: line.precio,
        fromVenta: true
      });
    });
    updateDock();
  }

  function renderSaleLines() {
    var box = $('pv2DevFromVenta');
    if (!box) return;
    if (!state.saleLines.length) {
      box.innerHTML = state.tipo === 'sin_comprobante'
        ? ''
        : '<p class="pv2-hint">No hay productos pendientes de devolver en este vale.</p>';
      return;
    }
    box.innerHTML = state.saleLines.map(function (line, idx) {
      return (
        '<div class="pv2-card' + (line.selected ? ' is-on' : '') + '" data-sale-idx="' + idx + '">' +
          '<div class="pv2-card-top">' +
            '<label style="display:flex;gap:10px;align-items:flex-start;cursor:pointer;flex:1">' +
              '<input type="checkbox" class="pv2-check pv2-sale-chk" ' + (line.selected ? 'checked' : '') + '>' +
              '<span><span class="pv2-card-name">' + escapeHtml(line.nombre) + '</span>' +
              '<span class="pv2-card-code">' + escapeHtml(line.codigo) + ' · máx ' + line.max + '</span></span>' +
            '</label>' +
            '<span class="pv2-card-price">' + money(line.precio) + '</span>' +
          '</div>' +
          (line.selected
            ? '<div class="pv2-card-qty">' +
                '<button type="button" data-sale-minus="' + idx + '">−</button>' +
                '<input type="number" min="1" max="' + line.max + '" value="' + line.cantidad + '" data-sale-qty="' + idx + '">' +
                '<button type="button" data-sale-plus="' + idx + '">+</button>' +
              '</div>'
            : '') +
        '</div>'
      );
    }).join('');
  }

  function renderExtraDev() {
    var box = $('pv2DevExtra');
    if (!box) return;
    var extras = state.devueltos.filter(function (r) { return !r.fromVenta; });
    box.innerHTML = extras.map(function (r, i) {
      return cardHtml(r, 'dev', i);
    }).join('');
  }

  function renderEnt() {
    var box = $('pv2EntCards');
    if (!box) return;
    box.innerHTML = state.entregados.map(function (r, i) {
      return cardHtml(r, 'ent', i);
    }).join('') || '<p class="pv2-hint">Aún no agrega productos.</p>';
  }

  function cardHtml(r, kind, i) {
    return (
      '<div class="pv2-card is-on">' +
        '<div class="pv2-card-top">' +
          '<div><div class="pv2-card-name">' + escapeHtml(r.nombre) + '</div>' +
          '<div class="pv2-card-code">' + escapeHtml(r.codigo) + '</div></div>' +
          '<span class="pv2-card-price">' + money(r.precio) + '</span>' +
        '</div>' +
        '<div class="pv2-card-qty">' +
          '<button type="button" data-' + kind + '-minus="' + i + '">−</button>' +
          '<input type="number" min="1" value="' + r.cantidad + '" data-' + kind + '-qty="' + i + '">' +
          '<button type="button" data-' + kind + '-plus="' + i + '">+</button>' +
        '</div>' +
        '<button type="button" class="pv2-card-del" data-' + kind + '-del="' + i + '">Eliminar</button>' +
      '</div>'
    );
  }

  function escapeHtml(s) {
    return String(s || '')
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;');
  }

  function applyVenta(venta) {
    state.venta = venta;
    state.clienteId = venta.cliente_id || null;
    state.saldoFavor = Number(venta.saldo_favor || 0);
    state.saleLines = (venta.detalles || []).map(function (d) {
      var max = Math.max(0, Number(d.cantidad) || 0);
      var desc = Number(d.descuento || 0);
      var pu = Number(d.precio_unitario || d.precio || 0);
      if (desc > 0) pu = pu * (1 - desc / 100);
      var codigo = (d.codigo_barra || d.codigo_interno || d.codigo || '').trim();
      return {
        codigo: codigo,
        nombre: d.nombre || '',
        precio: pu,
        max: max,
        cantidad: max > 0 ? Math.min(1, max) : 0,
        selected: false
      };
    }).filter(function (x) { return x.codigo && x.max > 0; });
    state.devueltos = [];
    state.entregados = [];

    var card = $('pv2VentaCard');
    card.hidden = false;
    card.innerHTML =
      '<h3>' + escapeHtml(venta.cliente_nombre || 'Mostrador') + '</h3>' +
      '<p>Vale ' + escapeHtml(venta.folio || ('VL' + String(venta.id).padStart(6, '0'))) +
      (venta.fecha ? ' · ' + escapeHtml(venta.fecha) : '') +
      (venta.monto_total != null ? ' · ' + money(venta.monto_total) : '') + '</p>';
    $('pv2Go3').disabled = false;
    $('pv2ListaVentas').hidden = true;
    showMsg($('pv2BuscarMsg'), '');
    renderSaleLines();
    updateDock();
  }

  function buscarVenta() {
    var q = ($('pv2Query').value || '').trim();
    if (!q) {
      showMsg($('pv2BuscarMsg'), 'Indique folio o RUT.', true);
      return;
    }
    showMsg($('pv2BuscarMsg'), 'Buscando…');
    fetch(URLS.buscar + '?q=' + encodeURIComponent(q), {
      credentials: 'same-origin',
      headers: { 'X-Requested-With': 'XMLHttpRequest' }
    })
      .then(function (r) { return r.json(); })
      .then(function (data) {
        if (!data || !data.ok) {
          showMsg($('pv2BuscarMsg'), (data && data.mensaje) || 'No encontrado', true);
          return;
        }
        if (data.modo === 'venta' && data.venta) {
          applyVenta(data.venta);
          return;
        }
        var lista = data.ventas || [];
        var box = $('pv2ListaVentas');
        if (!lista.length) {
          showMsg($('pv2BuscarMsg'), 'Sin ventas para ese cliente.', true);
          box.hidden = true;
          return;
        }
        showMsg($('pv2BuscarMsg'), '');
        box.hidden = false;
        box.innerHTML = lista.map(function (v) {
          return (
            '<button type="button" data-vid="' + v.id + '">' +
              '<strong>' + escapeHtml(v.folio || ('#' + v.id)) + '</strong>' +
              '<span>' + escapeHtml(v.fecha || '') + ' · ' + money(v.monto_total) +
              (v.estado ? ' · ' + escapeHtml(v.estado) : '') + '</span>' +
            '</button>'
          );
        }).join('');
      })
      .catch(function (e) {
        showMsg($('pv2BuscarMsg'), e.message || 'Error de red', true);
      });
  }

  function loadVentaId(id) {
    fetch(URLS.venta + '/' + id, {
      credentials: 'same-origin',
      headers: { 'X-Requested-With': 'XMLHttpRequest' }
    })
      .then(function (r) { return r.json(); })
      .then(function (data) {
        if (!data || !data.ok || !data.venta) {
          showMsg($('pv2BuscarMsg'), (data && data.mensaje) || 'No se pudo cargar la venta', true);
          return;
        }
        applyVenta(data.venta);
      });
  }

  function fetchProducto(codigo) {
    return fetch(URLS.producto + '/' + encodeURIComponent(codigo), {
      credentials: 'same-origin',
      headers: { 'X-Requested-With': 'XMLHttpRequest' }
    }).then(function (r) { return r.json(); });
  }

  function addProducto(kind, codigo) {
    codigo = String(codigo || '').trim();
    if (!codigo) return;
    fetchProducto(codigo).then(function (data) {
      if (!data || !data.ok) {
        alert((data && data.mensaje) || 'Producto no encontrado');
        return;
      }
      var p = data.producto || data;
      var item = {
        codigo: (p.codigo_barra || p.codigo_interno || codigo || '').trim(),
        nombre: p.nombre || codigo,
        precio: Number(p.precio || p.precio_venta || 0),
        cantidad: 1,
        max: null,
        fromVenta: false
      };
      if (kind === 'dev') {
        state.devueltos.push(item);
        renderExtraDev();
        $('pv2DevScan').value = '';
      } else {
        state.entregados.push(item);
        renderEnt();
        $('pv2EntScan').value = '';
      }
      updateDock();
    }).catch(function (e) { alert(e.message || e); });
  }

  function calcMontos() {
    var d = tot(state.devueltos);
    var e = tot(state.entregados);
    var usarSaldo = 0;
    var montoPagado = 0;
    var montoDevuelto = 0;
    var netoBase = e - d;
    var modo = (document.querySelector('input[name="pv2Comp"]:checked') || {}).value || 'efectivo';

    if (netoBase > 0) {
      montoPagado = netoBase;
      usarSaldo = 0;
      montoDevuelto = 0;
    } else {
      var favor = Math.abs(netoBase);
      if (modo === 'saldo') {
        montoDevuelto = 0;
      } else if (modo === 'mixto') {
        montoDevuelto = Math.min(favor, Number($('pv2MixEfectivo').value || 0));
      } else {
        montoDevuelto = favor;
      }
    }
    return {
      totalDev: d,
      totalEnt: e,
      neto: e - d - usarSaldo,
      montoPagado: montoPagado,
      montoDevuelto: montoDevuelto,
      usarSaldo: usarSaldo,
      modo: modo
    };
  }

  function renderConfirm() {
    var m = calcMontos();
    var box = $('pv2Resumen');
    var linesDev = state.devueltos.map(function (r) {
      return '<div class="pv2-resumen-line"><span>' + escapeHtml(r.nombre) + ' ×' + r.cantidad +
        '</span><strong>' + money(r.precio * r.cantidad) + '</strong></div>';
    }).join('');
    var linesEnt = state.entregados.map(function (r) {
      return '<div class="pv2-resumen-line"><span>' + escapeHtml(r.nombre) + ' ×' + r.cantidad +
        '</span><strong>' + money(r.precio * r.cantidad) + '</strong></div>';
    }).join('');
    box.innerHTML =
      '<h3>Devuelve</h3>' + (linesDev || '<p class="pv2-hint">—</p>') +
      '<hr class="pv2-resumen-sep">' +
      (state.tipo === 'devolucion' ? '' : ('<h3>Lleva</h3>' + (linesEnt || '<p class="pv2-hint">—</p>') + '<hr class="pv2-resumen-sep">')) +
      '<div class="pv2-resumen-line"><span>Total devuelve</span><strong>' + money(m.totalDev) + '</strong></div>' +
      (state.tipo === 'devolucion' ? '' : '<div class="pv2-resumen-line"><span>Total lleva</span><strong>' + money(m.totalEnt) + '</strong></div>') +
      '<div class="pv2-resumen-line"><span>' + (m.neto > 0 ? 'Cliente paga' : m.neto < 0 ? 'A favor del cliente' : 'Compensado') +
      '</span><strong>' + money(Math.abs(m.neto)) + '</strong></div>';

    var comp = $('pv2CompBlock');
    var label = $('pv2CompLabel');
    var opts = $('pv2CompOpts');
    var fields = $('pv2CompFields');
    var btn = $('pv2Registrar');
    if (m.neto > 0) {
      label.textContent = 'Cliente debe pagar';
      opts.hidden = true;
      fields.hidden = true;
      btn.textContent = 'Registrar · cobra ' + money(m.neto);
    } else if (m.neto < 0) {
      label.textContent = '¿Cómo devolver el dinero?';
      opts.hidden = false;
      fields.hidden = m.modo !== 'mixto';
      if (!state.clienteId) {
        $('pv2SaldoHint').hidden = false;
        $('pv2SaldoHint').textContent = 'Sin cliente en el vale: solo efectivo (no se puede generar saldo a favor).';
        document.querySelectorAll('input[name="pv2Comp"]').forEach(function (r) {
          if (r.value !== 'efectivo') r.disabled = true;
          else r.checked = true;
        });
      } else {
        $('pv2SaldoHint').hidden = true;
        document.querySelectorAll('input[name="pv2Comp"]').forEach(function (r) { r.disabled = false; });
      }
      btn.textContent = 'Registrar operación';
    } else {
      label.textContent = 'Cambio compensado';
      opts.hidden = true;
      fields.hidden = true;
      btn.textContent = 'Registrar cambio';
    }
    var back = $('pv2Back5');
    if (back) back.setAttribute('data-goto', state.tipo === 'devolucion' ? '3' : '4');
  }

  function registrar() {
    if (!state.devueltos.length) {
      alert('Seleccione al menos un producto a devolver.');
      return;
    }
    if (state.tipo === 'cambio' && !state.entregados.length) {
      if (!confirm('Cambio sin producto entregado. ¿Registrar como devolución?')) return;
    }
    var m = calcMontos();
    if (m.neto < 0 && !state.clienteId && m.modo !== 'efectivo') {
      alert('Sin cliente solo puede devolver en efectivo.');
      return;
    }
    if (m.neto < 0 && m.modo === 'saldo' && !state.clienteId) {
      alert('Seleccione un vale con cliente para dejar saldo a favor.');
      return;
    }
    // Recalcular montos finales según modo
    if (m.neto < 0) {
      var favor = Math.abs(m.neto);
      if (m.modo === 'saldo') {
        m.montoDevuelto = 0;
      } else if (m.modo === 'mixto') {
        m.montoDevuelto = Math.min(favor, Number($('pv2MixEfectivo').value || 0));
      } else {
        m.montoDevuelto = favor;
      }
      m.montoPagado = 0;
    }

    var form = document.createElement('form');
    form.method = 'POST';
    form.action = URLS.registrar;
    function hid(name, val) {
      var i = document.createElement('input');
      i.type = 'hidden';
      i.name = name;
      i.value = val;
      form.appendChild(i);
    }
    hid('ui_origen', 'postventa');
    hid('lineas_devueltas', state.devueltos.map(rowLine).join('\n'));
    hid('lineas_entregadas', state.entregados.map(rowLine).join('\n'));
    hid('monto_pagado', String(Math.round(m.montoPagado)));
    hid('monto_devuelto_efectivo', String(Math.round(m.montoDevuelto)));
    hid('usar_saldo_favor', '0');
    hid('observacion', ($('pv2Obs').value || '').trim());
    if (state.venta && state.venta.id) hid('venta_origen_id', String(state.venta.id));
    if (state.clienteId) hid('cliente_id', String(state.clienteId));
    document.body.appendChild(form);
    form.submit();
  }

  // —— Events ——
  document.querySelectorAll('.pv2-choice').forEach(function (btn) {
    btn.addEventListener('click', function () {
      state.tipo = btn.getAttribute('data-tipo');
      document.querySelectorAll('.pv2-choice').forEach(function (b) {
        b.classList.toggle('is-selected', b === btn);
      });
      if (state.tipo === 'sin_comprobante') {
        state.venta = null;
        state.clienteId = null;
        state.saleLines = [];
        $('pv2Q2').textContent = 'Sin comprobante · puede saltar la búsqueda';
        $('pv2VentaCard').hidden = true;
        $('pv2Go3').disabled = false;
        $('pv2DevScanWrap').hidden = false;
      } else {
        $('pv2Q2').textContent = 'Buscar venta';
        $('pv2Go3').disabled = !state.venta;
      }
      goStep(2);
      setTimeout(function () { $('pv2Query').focus(); }, 50);
    });
  });

  document.querySelectorAll('[data-goto]').forEach(function (btn) {
    btn.addEventListener('click', function () {
      goStep(Number(btn.getAttribute('data-goto')));
    });
  });
  document.querySelectorAll('.pv2-step').forEach(function (btn) {
    btn.addEventListener('click', function () {
      var s = Number(btn.getAttribute('data-step'));
      if (s <= state.step || (state.tipo && s === 2)) goStep(s);
    });
  });

  $('pv2Buscar').addEventListener('click', buscarVenta);
  $('pv2Query').addEventListener('keydown', function (ev) {
    if (ev.key === 'Enter') { ev.preventDefault(); buscarVenta(); }
  });

  $('pv2ListaVentas').addEventListener('click', function (ev) {
    var b = ev.target.closest('[data-vid]');
    if (!b) return;
    loadVentaId(b.getAttribute('data-vid'));
  });

  $('pv2Go3').addEventListener('click', function () { goStep(3); renderSaleLines(); renderExtraDev(); updateDock(); });
  $('pv2Go4').addEventListener('click', function () {
    if (!state.devueltos.length) { alert('Seleccione qué se devuelve.'); return; }
    if (state.tipo === 'devolucion') goStep(5);
    else goStep(4);
  });
  $('pv2Go5').addEventListener('click', function () { goStep(5); });

  $('pv2DevFromVenta').addEventListener('click', function (ev) {
    var card = ev.target.closest('[data-sale-idx]');
    if (!card) return;
    var idx = Number(card.getAttribute('data-sale-idx'));
    var line = state.saleLines[idx];
    if (!line) return;
    if (ev.target.classList.contains('pv2-sale-chk') || ev.target.closest('label')) {
      // checkbox change handled below
    }
    if (ev.target.hasAttribute('data-sale-minus')) {
      line.cantidad = Math.max(1, line.cantidad - 1);
      syncDevFromSaleChecks(); renderSaleLines(); return;
    }
    if (ev.target.hasAttribute('data-sale-plus')) {
      line.cantidad = Math.min(line.max, line.cantidad + 1);
      syncDevFromSaleChecks(); renderSaleLines(); return;
    }
  });
  $('pv2DevFromVenta').addEventListener('change', function (ev) {
    var card = ev.target.closest('[data-sale-idx]');
    if (!card) return;
    var idx = Number(card.getAttribute('data-sale-idx'));
    var line = state.saleLines[idx];
    if (!line) return;
    if (ev.target.classList.contains('pv2-sale-chk')) {
      line.selected = ev.target.checked;
      if (line.selected && line.cantidad < 1) line.cantidad = 1;
      syncDevFromSaleChecks(); renderSaleLines(); return;
    }
    if (ev.target.hasAttribute('data-sale-qty')) {
      var q = parseInt(ev.target.value, 10) || 1;
      line.cantidad = Math.max(1, Math.min(line.max, q));
      syncDevFromSaleChecks(); renderSaleLines();
    }
  });

  function bindList(boxId, kind) {
    var box = $(boxId);
    if (!box) return;
    box.addEventListener('click', function (ev) {
      var arr = kind === 'dev' ? state.devueltos.filter(function (r) { return !r.fromVenta; }) : state.entregados;
      var full = kind === 'dev' ? state.devueltos : state.entregados;
      if (ev.target.hasAttribute('data-' + kind + '-del')) {
        var di = Number(ev.target.getAttribute('data-' + kind + '-del'));
        var item = arr[di];
        var ix = full.indexOf(item);
        if (ix >= 0) full.splice(ix, 1);
        if (kind === 'dev') renderExtraDev(); else renderEnt();
        updateDock();
        return;
      }
      if (ev.target.hasAttribute('data-' + kind + '-minus') || ev.target.hasAttribute('data-' + kind + '-plus')) {
        var attr = ev.target.hasAttribute('data-' + kind + '-minus') ? 'minus' : 'plus';
        var i = Number(ev.target.getAttribute('data-' + kind + '-' + attr));
        var it = arr[i];
        if (!it) return;
        if (attr === 'minus') it.cantidad = Math.max(1, it.cantidad - 1);
        else it.cantidad += 1;
        if (kind === 'dev') renderExtraDev(); else renderEnt();
        updateDock();
      }
    });
    box.addEventListener('change', function (ev) {
      if (!ev.target.hasAttribute('data-' + kind + '-qty')) return;
      var arr = kind === 'dev' ? state.devueltos.filter(function (r) { return !r.fromVenta; }) : state.entregados;
      var i = Number(ev.target.getAttribute('data-' + kind + '-qty'));
      var it = arr[i];
      if (!it) return;
      it.cantidad = Math.max(1, parseInt(ev.target.value, 10) || 1);
      updateDock();
    });
  }
  bindList('pv2DevExtra', 'dev');
  bindList('pv2EntCards', 'ent');

  $('pv2DevAdd').addEventListener('click', function () { addProducto('dev', $('pv2DevScan').value); });
  $('pv2DevScan').addEventListener('keydown', function (ev) {
    if (ev.key === 'Enter') { ev.preventDefault(); addProducto('dev', $('pv2DevScan').value); }
  });
  $('pv2EntAdd').addEventListener('click', function () { addProducto('ent', $('pv2EntScan').value); });
  $('pv2EntScan').addEventListener('keydown', function (ev) {
    if (ev.key === 'Enter') { ev.preventDefault(); addProducto('ent', $('pv2EntScan').value); }
  });

  document.querySelectorAll('input[name="pv2Comp"]').forEach(function (r) {
    r.addEventListener('change', renderConfirm);
  });
  var mix = $('pv2MixEfectivo');
  if (mix) mix.addEventListener('input', renderConfirm);

  $('pv2Registrar').addEventListener('click', registrar);

  var nueva = $('pv2NuevaOp');
  if (nueva) {
    nueva.addEventListener('click', function () {
      window.location.href = window.location.pathname;
    });
  }

  updateDock();
})();
