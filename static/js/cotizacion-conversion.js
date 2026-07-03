/**
 * Asistente cotización → venta POS (preview + convertir JSON).
 */
(function () {
  'use strict';

  var btnAbrir = document.getElementById('btnAbrirAsistenteConversion');
  var modalEl = document.getElementById('modalCotConversion');
  if (!btnAbrir || !modalEl || typeof bootstrap === 'undefined') return;

  var modal = bootstrap.Modal.getOrCreateInstance(modalEl);
  var cotId = parseInt(btnAbrir.getAttribute('data-cot-id') || '0', 10);
  var state = {
    preview: null,
    lineas: [],
    montoAcordado: 0,
    diasEntrega: 5,
  };

  var el = {
    loading: document.getElementById('cotConvLoading'),
    error: document.getElementById('cotConvError'),
    workspace: document.getElementById('cotConvWorkspace'),
    cliente: document.getElementById('cotConvCliente'),
    body: document.getElementById('cotConvLineasBody'),
    totalCot: document.getElementById('cotConvTotalCot'),
    totalVenta: document.getElementById('cotConvTotalVenta'),
    deltaRow: document.getElementById('cotConvDeltaRow'),
    delta: document.getElementById('cotConvDelta'),
    modoProyecto: document.getElementById('cotConvModoProyecto'),
    proyectoAlert: document.getElementById('cotConvProyectoAlert'),
    confirmacion: document.getElementById('cotConvConfirmacion'),
    btnConfirmar: document.getElementById('cotConvBtnConfirmar'),
    subtitulo: document.getElementById('cotConvSubtitulo'),
  };

  function fmt(n) {
    return '$' + Math.round(Number(n) || 0).toLocaleString('es-CL');
  }

  function semaforoIcon(sem) {
    if (sem === 'ok') return '🟢';
    if (sem === 'a_pedido') return '⏳';
    if (sem === 'sin_sku') return '⚠️';
    return '🔴';
  }

  function recalcSemaforo(ln) {
    if (!ln.incluir) return 'excluida';
    if (ln.sin_sku) return 'sin_sku';
    if (ln.a_pedido) return 'a_pedido';
    if (ln.stock_ok) return 'ok';
    return 'falta_stock';
  }

  function subtotalBrutoEst(ln) {
    var cant = Math.max(1, parseFloat(ln.cantidad) || 1);
    var neto = Math.max(0, Math.round(cant * (ln.precio_unitario || 0) - (ln.descuento || 0)));
    var iva = Math.round(neto * 0.19);
    return neto + iva;
  }

  function renderLineas() {
    if (!el.body) return;
    el.body.innerHTML = '';
    var rowIdx = 0;
    state.lineas.forEach(function (ln, idx) {
      if (!ln.incluir) return;
      var sem = recalcSemaforo(ln);
      rowIdx += 1;
      var tr = document.createElement('tr');
      tr.className = 'cot-conv-row' + (ln.a_pedido ? ' cot-conv-row--pedido' : '') + (sem === 'falta_stock' || sem === 'sin_sku' ? ' cot-conv-row--alerta' : '');
      tr.innerHTML =
        '<td class="cot-conv-sem">' + semaforoIcon(sem) + '</td>' +
        '<td class="cot-conv-articulo">' +
        '<div class="cot-conv-articulo-nombre">' + escapeHtml(ln.nombre) + '</div>' +
        (ln.a_pedido ? '<span class="cot-conv-tag cot-conv-tag--pedido">A pedido ~' + state.diasEntrega + ' d</span>' : '') +
        (ln.sin_sku ? '<span class="cot-conv-tag cot-conv-tag--danger">Sin SKU</span>' : '') +
        '</td>' +
        '<td class="text-end"><input type="number" min="0.01" step="1" class="form-control form-control-sm text-end cot-conv-input cot-conv-qty" data-idx="' + idx + '" value="' + ln.cantidad + '"></td>' +
        '<td class="text-end"><input type="number" min="0" step="1" class="form-control form-control-sm text-end cot-conv-input cot-conv-pu" data-idx="' + idx + '" value="' + Math.round(ln.precio_unitario) + '"></td>' +
        '<td class="text-end cot-conv-stock">' + (ln.sin_sku ? '—' : ln.stock_disponible + ' / ' + ln.stock_requiere) + '</td>' +
        '<td><div class="cot-conv-acciones">' +
        '<button type="button" class="btn btn-sm cot-conv-btn-quitar cot-conv-quitar" data-idx="' + idx + '" title="Quitar línea">−</button>' +
        '<button type="button" class="btn btn-sm cot-conv-btn-pedido cot-conv-pedido" data-idx="' + idx + '" title="Cliente espera">⏳</button>' +
        '</div></td>';
      el.body.appendChild(tr);
    });
    bindLineEvents();
    updateTotales();
  }

  function escapeHtml(s) {
    return String(s || '').replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
  }

  function bindLineEvents() {
    el.body.querySelectorAll('.cot-conv-qty').forEach(function (inp) {
      inp.addEventListener('change', onLineInput);
    });
    el.body.querySelectorAll('.cot-conv-pu').forEach(function (inp) {
      inp.addEventListener('change', onLineInput);
    });
    el.body.querySelectorAll('.cot-conv-quitar').forEach(function (btn) {
      btn.addEventListener('click', function () {
        var idx = parseInt(btn.getAttribute('data-idx'), 10);
        state.lineas[idx].incluir = false;
        state.lineas[idx].a_pedido = false;
        renderLineas();
      });
    });
    el.body.querySelectorAll('.cot-conv-pedido').forEach(function (btn) {
      btn.addEventListener('click', function () {
        var idx = parseInt(btn.getAttribute('data-idx'), 10);
        state.lineas[idx].a_pedido = !state.lineas[idx].a_pedido;
        renderLineas();
      });
    });
  }

  function onLineInput(e) {
    var idx = parseInt(e.target.getAttribute('data-idx'), 10);
    var ln = state.lineas[idx];
    if (e.target.classList.contains('cot-conv-qty')) {
      ln.cantidad = Math.max(0.01, parseFloat(e.target.value) || 1);
      ln.stock_requiere = Math.max(1, Math.round(ln.cantidad));
      ln.stock_ok = ln.stock_disponible >= ln.stock_requiere;
    } else {
      ln.precio_unitario = Math.max(0, parseFloat(e.target.value) || 0);
    }
    renderLineas();
  }

  function lineasIncluidas() {
    return state.lineas.filter(function (l) { return l.incluir; });
  }

  function updateTotales() {
    var incl = lineasIncluidas();
    var totalVenta = incl.reduce(function (s, ln) { return s + subtotalBrutoEst(ln); }, 0);
    if (el.totalCot) el.totalCot.textContent = fmt(state.montoAcordado);
    if (el.totalVenta) el.totalVenta.textContent = fmt(totalVenta);
    var delta = totalVenta - state.montoAcordado;
    if (el.modoProyecto && el.modoProyecto.checked) {
      el.deltaRow.classList.remove('d-none');
      el.delta.textContent = fmt(delta);
      if (Math.abs(delta) > 1) {
        el.proyectoAlert.classList.remove('d-none');
        el.proyectoAlert.textContent =
          'Faltan ' + fmt(Math.abs(delta)) + ' para cuadrar el monto del proyecto. Ajuste precios o cantidades.';
      } else {
        el.proyectoAlert.classList.add('d-none');
      }
    } else {
      el.deltaRow.classList.add('d-none');
      el.proyectoAlert.classList.add('d-none');
    }
    var bloqueos = incl.some(function (ln) {
      return ln.sin_sku || (!ln.a_pedido && !ln.stock_ok);
    });
    var proyectoOk = !el.modoProyecto.checked || Math.abs(delta) <= 1;
    el.btnConfirmar.disabled = bloqueos || !incl.length || !el.confirmacion.checked || !proyectoOk;
  }

  function showError(msg) {
    el.loading.classList.add('d-none');
    el.workspace.classList.add('d-none');
    el.error.classList.remove('d-none');
    el.error.textContent = msg;
    el.btnConfirmar.disabled = true;
  }

  function loadPreview() {
    el.loading.classList.remove('d-none');
    el.workspace.classList.add('d-none');
    el.error.classList.add('d-none');
    el.btnConfirmar.disabled = true;
    el.confirmacion.checked = false;

    fetch('/api/cotizaciones/' + cotId + '/conversion-preview', { credentials: 'same-origin' })
      .then(function (r) { return r.json().then(function (j) { return { ok: r.ok, j: j }; }); })
      .then(function (res) {
        if (!res.ok || !res.j.ok) {
          showError((res.j && res.j.error) || 'No se pudo cargar el asistente.');
          return;
        }
        state.preview = res.j;
        state.diasEntrega = res.j.pos_dias_entrega_a_pedido || 5;
        state.montoAcordado = (res.j.totales && res.j.totales.total) || 0;
        state.lineas = (res.j.lineas || []).map(function (ln) {
          return Object.assign({}, ln, { incluir: ln.incluir !== false });
        });
        if (res.j.venta_abierta_id) {
          el.subtitulo.textContent = 'Ya hay una venta abierta #' + res.j.venta_abierta_id + ' — puede continuar en POS.';
        }
        var cot = res.j.cotizacion || {};
        el.cliente.textContent = (cot.cliente_nombre || 'Sin nombre') + (cot.cliente_rut ? ' · ' + cot.cliente_rut : '');
        if (el.modoProyecto) {
          el.modoProyecto.disabled = !cot.modo_proyecto_disponible;
          el.modoProyecto.checked = cot.estado === 'Aceptada';
        }
        el.loading.classList.add('d-none');
        el.workspace.classList.remove('d-none');
        renderLineas();
      })
      .catch(function () {
        showError('Error de red al cargar la cotización.');
      });
  }

  function buildPayload() {
    var lineas = lineasIncluidas().map(function (ln) {
      return {
        detalle_id: ln.detalle_id,
        producto_id: ln.producto_id,
        accion: 'incluir',
        cantidad: ln.cantidad,
        precio_unitario: ln.precio_unitario,
        descuento: ln.descuento || 0,
        a_pedido: !!ln.a_pedido,
      };
    });
    return {
      modo: 'pos',
      modo_proyecto: !!(el.modoProyecto && el.modoProyecto.checked),
      monto_acordado_clp: state.montoAcordado,
      confirmacion_cliente: true,
      lineas: lineas,
    };
  }

  function confirmarConversion() {
    el.btnConfirmar.disabled = true;
    el.btnConfirmar.innerHTML = '<span class="spinner-border spinner-border-sm me-1"></span>Abriendo POS…';
    fetch('/api/cotizaciones/' + cotId + '/convertir', {
      method: 'POST',
      credentials: 'same-origin',
      headers: { 'Content-Type': 'application/json', 'Accept': 'application/json' },
      body: JSON.stringify(buildPayload()),
    })
      .then(function (r) { return r.json().then(function (j) { return { ok: r.ok, j: j }; }); })
      .then(function (res) {
        if (!res.ok || !res.j.ok) {
          var err = (res.j && (res.j.errors && res.j.errors[0])) || (res.j && res.j.error) || 'Error al convertir.';
          showError(err);
          el.btnConfirmar.disabled = false;
          el.btnConfirmar.innerHTML = '<i class="fas fa-arrow-right-to-bracket me-1"></i>Abrir en POS';
          return;
        }
        window.location.href = res.j.redirect || '/punto_venta?cot_emitir_guia=1';
      })
      .catch(function () {
        showError('Error de red al convertir.');
        el.btnConfirmar.disabled = false;
        el.btnConfirmar.innerHTML = '<i class="fas fa-arrow-right-to-bracket me-1"></i>Abrir en POS';
      });
  }

  btnAbrir.addEventListener('click', function () {
    modal.show();
    loadPreview();
  });

  if (el.confirmacion) el.confirmacion.addEventListener('change', updateTotales);
  if (el.modoProyecto) el.modoProyecto.addEventListener('change', updateTotales);
  if (el.btnConfirmar) el.btnConfirmar.addEventListener('click', confirmarConversion);
})();
