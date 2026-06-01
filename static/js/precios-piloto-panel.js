/**
 * Panel carga mostrador piloto — precio SD + stock tienda/bodega.
 */
(function () {
  var productoActual = null;
  var inpPrecio = document.getElementById('inpPrecioSd');
  var inpStockT = document.getElementById('inpStockTienda');
  var inpStockB = document.getElementById('inpStockBodega');
  var inpSector = document.getElementById('inpSectorPiloto');
  var inpMotivo = document.getElementById('inpMotivoPiloto');
  var panel = document.getElementById('pilotoProducto');
  var alertEl = document.getElementById('pilotoAlert');
  var avisoPrevia = document.getElementById('pilotoAvisoCargaPrevia');
  var modoHint = document.getElementById('pilotoModoStockHint');
  var lblT = document.getElementById('lblStockTienda');
  var lblB = document.getElementById('lblStockBodega');
  var busquedaApi = null;

  function fmtCLP(n) {
    return 'CLP $' + Math.round(Number(n) || 0).toLocaleString('es-CL');
  }

  function modoStockActual() {
    var el = document.querySelector('input[name="pilotoModoStock"]:checked');
    return el ? el.value : 'inicial';
  }

  function setModoStock(modo) {
    var m = modo || 'inicial';
    var radio = document.querySelector('input[name="pilotoModoStock"][value="' + m + '"]');
    if (radio) radio.checked = true;
    syncModoStockUi();
  }

  function syncModoStockUi() {
    var modo = modoStockActual();
    if (modo === 'solo_precio') {
      if (inpStockT) inpStockT.disabled = true;
      if (inpStockB) inpStockB.disabled = true;
      if (modoHint) modoHint.textContent = 'Solo actualiza precio SD; no modifica stock.';
    } else if (modo === 'sumar') {
      if (inpStockT) inpStockT.disabled = false;
      if (inpStockB) inpStockB.disabled = false;
      if (lblT) lblT.textContent = 'Sumar tienda (+)';
      if (lblB) lblB.textContent = 'Sumar bodega (+)';
      if (modoHint) modoHint.textContent = 'Indique cuántas unidades encontró en esta sección (se suman al total).';
      if (inpStockT) inpStockT.placeholder = 'Ej: 5';
      if (inpStockB) inpStockB.placeholder = 'Ej: 0';
    } else if (modo === 'reemplazar') {
      if (inpStockT) inpStockT.disabled = false;
      if (inpStockB) inpStockB.disabled = false;
      if (lblT) lblT.textContent = 'Nuevo total tienda';
      if (lblB) lblB.textContent = 'Nuevo total bodega';
      if (modoHint) modoHint.textContent = 'Reemplaza el stock total en tienda/bodega (recuento completo).';
      if (inpStockT) inpStockT.placeholder = 'Total tienda';
      if (inpStockB) inpStockB.placeholder = 'Total bodega';
    } else {
      if (inpStockT) inpStockT.disabled = false;
      if (inpStockB) inpStockB.disabled = false;
      if (lblT) lblT.textContent = 'Stock tienda';
      if (lblB) lblB.textContent = 'Stock bodega';
      if (modoHint) modoHint.textContent = 'Primer conteo piloto: cantidad total en tienda y bodega.';
      if (inpStockT) inpStockT.placeholder = '0';
      if (inpStockB) inpStockB.placeholder = '0';
    }
  }

  function showAlert(msg, kind) {
    alertEl.textContent = msg;
    alertEl.className = 'alert alert-' + (kind || 'info');
    alertEl.classList.remove('d-none');
  }

  function hideAlert() {
    alertEl.classList.add('d-none');
  }

  function renderProducto(p) {
    productoActual = p;
    panel.classList.remove('d-none');
    document.getElementById('pilotoNombre').textContent = p.nombre || '—';
    document.getElementById('pilotoCodigo').textContent = p.codigo || '—';
    document.getElementById('pilotoCategoria').textContent = p.categoria || '—';
    document.getElementById('pilotoCosto').textContent = fmtCLP(p.costo);
    document.getElementById('pilotoLista').textContent = fmtCLP(p.precio_lista);
    document.getElementById('pilotoMayoreo').textContent = fmtCLP(p.precio_mayoreo);
    var ef = document.getElementById('pilotoEfectivo');
    ef.textContent = fmtCLP(p.precio_venta_sd || p.precio_efectivo);
    ef.className = p.sin_precio ? 'fw-bold text-danger' : 'fw-bold text-success';
    document.getElementById('pilotoStTienda').textContent = String(p.stock_tienda || 0);
    document.getElementById('pilotoStBodega').textContent = String(p.stock_bodega || 0);

    inpPrecio.value = p.precio_efectivo > 0 ? String(Math.round(p.precio_efectivo)) : '';

    var ult = p.ultima_carga_piloto;
    if (p.tiene_carga_previa && ult && avisoPrevia) {
      avisoPrevia.classList.remove('d-none');
      avisoPrevia.innerHTML =
        '<strong>Ya hay carga piloto anterior</strong> (' +
        (ult.fecha || '—') +
        ', ' +
        (ult.usuario || '—') +
        '): Tienda <strong>' +
        (ult.stock_tienda_despues || 0) +
        '</strong>, Bodega <strong>' +
        (ult.stock_bodega_despues || 0) +
        '</strong>' +
        (ult.sector && ult.sector !== '—' ? ' · sector «' + ult.sector + '»' : '') +
        '. Elija <em>Sumar sección</em> si encontró más unidades en otro lugar.';
      setModoStock(p.modo_stock_sugerido || 'sumar');
      if (inpStockT) inpStockT.value = '';
      if (inpStockB) inpStockB.value = '';
    } else {
      if (avisoPrevia) avisoPrevia.classList.add('d-none');
      setModoStock('inicial');
      if (inpStockT) inpStockT.value = String(p.stock_tienda || 0);
      if (inpStockB) inpStockB.value = String(p.stock_bodega || 0);
    }

    hideAlert();
    inpPrecio.focus();
    inpPrecio.select();
  }

  function prependBitacora(row) {
    var tbody = document.getElementById('pilotoBitacoraBody');
    if (!tbody) return;
    var tr = document.createElement('tr');
    tr.innerHTML =
      '<td class="text-nowrap small">' +
      row.fecha +
      '</td><td class="small">' +
      row.nombre +
      '</td><td class="text-nowrap small">' +
      row.precio +
      ' ' +
      (row.stock || '') +
      '</td><td class="small text-muted">' +
      row.usuario +
      '</td>';
    if (tbody.querySelector('td[colspan]')) tbody.innerHTML = '';
    tbody.insertBefore(tr, tbody.firstChild);
  }

  function guardar() {
    if (!productoActual) {
      showAlert('Busque un producto primero.', 'warning');
      return;
    }
    var modo = modoStockActual();
    var body = {
      producto_id: productoActual.id,
      precio_venta: (inpPrecio.value || '').trim(),
      motivo: (inpMotivo.value || '').trim(),
      modo_stock: modo,
      sector_ubicacion: (inpSector.value || '').trim(),
    };
    if (modo !== 'solo_precio') {
      if (inpStockT && inpStockT.value !== '') body.stock_tienda = inpStockT.value;
      if (inpStockB && inpStockB.value !== '') body.stock_bodega = inpStockB.value;
    }
    fetch('/api/precios/piloto/guardar', {
      method: 'POST',
      credentials: 'same-origin',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    })
      .then(function (r) {
        return r.json().then(function (data) {
          return { ok: r.ok, data: data };
        });
      })
      .then(function (res) {
        var data = res.data;
        if (!res.ok || !data.ok) {
          showAlert(data.error || data.mensaje || 'No se pudo guardar', 'danger');
          return;
        }
        if (data.sin_cambio) {
          showAlert('Sin cambios.', 'info');
          return;
        }
        renderProducto(data.producto);
        var msg = 'Guardado';
        if (data.precio_nuevo) msg += ' · SD ' + fmtCLP(data.precio_nuevo);
        if (data.stock) msg += ' · T' + data.stock.tienda + ' B' + data.stock.bodega;
        showAlert(msg, 'success');
        if (data.bitacora_row) prependBitacora(data.bitacora_row);
        if (busquedaApi && busquedaApi.focus) busquedaApi.focus();
      })
      .catch(function () {
        showAlert('Error de red al guardar.', 'danger');
      });
  }

  document.querySelectorAll('input[name="pilotoModoStock"]').forEach(function (el) {
    el.addEventListener('change', syncModoStockUi);
  });

  window.addEventListener('piloto:producto-seleccionado', function (ev) {
    if (ev.detail && ev.detail.producto) renderProducto(ev.detail.producto);
  });

  window.addEventListener('piloto:busqueda-error', function (ev) {
    showAlert((ev.detail && ev.detail.message) || 'Error al buscar.', 'warning');
  });

  if (inpPrecio) {
    inpPrecio.addEventListener('keydown', function (ev) {
      if (ev.key === 'Enter') {
        ev.preventDefault();
        guardar();
      }
    });
  }
  var btn = document.getElementById('btnGuardarPiloto');
  if (btn) btn.addEventListener('click', guardar);

  if (window.PreciosPilotoBusqueda) {
    busquedaApi = window.PreciosPilotoBusqueda.init();
  }

  var q0 = (new URLSearchParams(window.location.search).get('codigo') || {{ codigo_inicial|tojson }}).trim();
  if (q0 && busquedaApi && busquedaApi.buscar) {
    var inp = document.getElementById('posBuscarManual');
    if (inp) inp.value = q0;
    busquedaApi.buscar(q0, { autoSeleccionar: true, permitirCorto: true });
  }

  syncModoStockUi();
})();
