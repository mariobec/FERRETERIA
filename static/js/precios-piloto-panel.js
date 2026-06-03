/**
 * Panel carga mostrador piloto — precio SD + stock tienda/bodega.
 */
(function () {
  var STORAGE_FACTURA = 'piloto_sd_numero_factura';
  var STORAGE_GUIA = 'piloto_sd_numero_guia';
  var productoActual = null;
  var inpPrecio;
  var inpStockT;
  var inpStockB;
  var inpSector;
  var inpMotivo;
  var inpFactura;
  var inpGuia;
  var panel;
  var alertEl;
  var avisoPrevia;
  var avisoCosto;
  var modoHint;
  var lblT;
  var lblB;
  var busquedaApi = null;

  function enlazarDom() {
    inpPrecio = document.getElementById('inpPrecioSd');
    inpStockT = document.getElementById('inpStockTienda');
    inpStockB = document.getElementById('inpStockBodega');
    inpSector = document.getElementById('inpSectorPiloto');
    inpMotivo = document.getElementById('inpMotivoPiloto');
    inpFactura = document.getElementById('inpNumeroFacturaPiloto');
    inpGuia = document.getElementById('inpNumeroGuiaPiloto');
    panel = document.getElementById('pilotoProducto');
    alertEl = document.getElementById('pilotoAlert');
    avisoPrevia = document.getElementById('pilotoAvisoCargaPrevia');
    avisoCosto = document.getElementById('pilotoAvisoCosto');
    modoHint = document.getElementById('pilotoModoStockHint');
    lblT = document.getElementById('lblStockTienda');
    lblB = document.getElementById('lblStockBodega');
  }

  function fmtCLP(n) {
    return 'CLP $' + Math.round(Number(n) || 0).toLocaleString('es-CL');
  }

  function leerRefDocumento(inp) {
    if (!inp) return '';
    return String(inp.value || '').trim().slice(0, 64);
  }

  function persistirRefsDocumento() {
    try {
      if (inpFactura) sessionStorage.setItem(STORAGE_FACTURA, leerRefDocumento(inpFactura));
      if (inpGuia) sessionStorage.setItem(STORAGE_GUIA, leerRefDocumento(inpGuia));
    } catch (e) {
      /* sessionStorage no disponible */
    }
  }

  function restaurarRefsDocumento() {
    try {
      if (inpFactura) {
        var f = sessionStorage.getItem(STORAGE_FACTURA);
        if (f) inpFactura.value = f;
      }
      if (inpGuia) {
        var g = sessionStorage.getItem(STORAGE_GUIA);
        if (g) inpGuia.value = g;
      }
    } catch (e) {
      /* ignore */
    }
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
    if (!alertEl) return;
    alertEl.textContent = msg;
    alertEl.className = 'alert alert-' + (kind || 'info');
    alertEl.classList.remove('d-none');
  }

  function hideAlert() {
    if (!alertEl) return;
    alertEl.classList.add('d-none');
  }

  function prepararSiguienteEscaneo() {
    var api = busquedaApi || window.__preciosPilotoBusquedaApi;
    if (api && api.prepararEscaneo) {
      api.prepararEscaneo();
      return;
    }
    var form = document.getElementById('formBusquedaPreciosPiloto');
    var inp = form ? form.querySelector('#posBuscarManual') : document.getElementById('posBuscarManual');
    if (inp) {
      inp.value = '';
      inp.focus();
    }
  }

  /** Oculta ficha y vacía campos tras guardar — solo queda el aviso superior. */
  function limpiarFormularioPiloto() {
    productoActual = null;
    if (panel) panel.classList.add('d-none');
    /* factura/guía no se limpian — misma recepción */
    var ids = [
      'pilotoNombre',
      'pilotoCodigo',
      'pilotoCategoria',
      'pilotoCosto',
      'pilotoLista',
      'pilotoMayoreo',
      'pilotoEfectivo',
      'pilotoStTienda',
      'pilotoStBodega',
    ];
    ids.forEach(function (id) {
      var el = document.getElementById(id);
      if (!el) return;
      el.textContent = '—';
      if (id === 'pilotoEfectivo') el.className = 'fw-bold';
      if (id === 'pilotoCosto') el.className = '';
    });
    if (avisoPrevia) {
      avisoPrevia.classList.add('d-none');
      avisoPrevia.textContent = '';
    }
    if (avisoCosto) {
      avisoCosto.classList.add('d-none');
      avisoCosto.textContent = '';
    }
    if (inpPrecio) inpPrecio.value = '';
    if (inpStockT) {
      inpStockT.value = '';
      inpStockT.disabled = false;
    }
    if (inpStockB) {
      inpStockB.value = '';
      inpStockB.disabled = false;
    }
    if (inpSector) inpSector.value = '';
    setModoStock('inicial');
    syncModoStockUi();
  }

  function renderProducto(p, opts) {
    opts = opts || {};
    productoActual = p;
    if (!panel) return;
    panel.classList.remove('d-none');
    document.getElementById('pilotoNombre').textContent = p.nombre || '—';
    document.getElementById('pilotoCodigo').textContent = p.codigo || '—';
    document.getElementById('pilotoCategoria').textContent = p.categoria || '—';
    var elCosto = document.getElementById('pilotoCosto');
    if (elCosto) {
      elCosto.textContent = fmtCLP(p.costo);
      elCosto.className = p.costo_incoherente ? 'text-danger fw-bold' : '';
    }
    if (avisoCosto) {
      if (p.costo_incoherente && p.costo_alerta) {
        avisoCosto.classList.remove('d-none');
        var marg = p.margen_catalogo_pct != null ? ' (margen catálogo ' + p.margen_catalogo_pct + '%)' : '';
        avisoCosto.innerHTML =
          '<strong>Costo sospechoso</strong>' + marg + '. ' + p.costo_alerta +
          ' No use el costo mostrado para decidir precio SD; use lista o última factura.';
      } else {
        avisoCosto.classList.add('d-none');
        avisoCosto.textContent = '';
      }
    }
    document.getElementById('pilotoLista').textContent = fmtCLP(p.precio_lista);
    document.getElementById('pilotoMayoreo').textContent = fmtCLP(p.precio_mayoreo);
    var ef = document.getElementById('pilotoEfectivo');
    ef.textContent = fmtCLP(p.precio_venta_sd || p.precio_efectivo);
    ef.className = p.sin_precio ? 'fw-bold text-danger' : 'fw-bold text-success';
    document.getElementById('pilotoStTienda').textContent = String(p.stock_tienda || 0);
    document.getElementById('pilotoStBodega').textContent = String(p.stock_bodega || 0);

    if (p.precio_efectivo > 0) {
      inpPrecio.value = String(Math.round(p.precio_efectivo));
    } else if (p.precio_sd_sugerido > 0) {
      inpPrecio.value = String(p.precio_sd_sugerido);
    } else if (p.precio_lista > 0) {
      inpPrecio.value = String(Math.round(p.precio_lista));
    } else {
      inpPrecio.value = '';
    }

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
        (ult.numero_factura ? ' · F ' + ult.numero_factura : '') +
        (ult.numero_guia ? ' · G ' + ult.numero_guia : '') +
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
    if (opts.focoEnBusqueda) {
      prepararSiguienteEscaneo();
    } else if (!opts.sinFocoPrecio) {
      inpPrecio.focus();
      inpPrecio.select();
    }
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

  function leerStockParaGuardar(modo) {
    if (modo === 'solo_precio') {
      var out = {};
      if (inpStockT && String(inpStockT.value || '').trim() !== '') {
        out.stock_tienda = parseInt(inpStockT.value, 10);
      }
      if (inpStockB && String(inpStockB.value || '').trim() !== '') {
        out.stock_bodega = parseInt(inpStockB.value, 10);
      }
      return out;
    }
    var st = inpStockT ? parseInt(inpStockT.value, 10) : 0;
    var sb = inpStockB ? parseInt(inpStockB.value, 10) : 0;
    if (isNaN(st)) st = 0;
    if (isNaN(sb)) sb = 0;
    if (st < 0 || sb < 0) {
      return { error: 'Stock no puede ser negativo.' };
    }
    return { stock_tienda: st, stock_bodega: sb };
  }

  function guardar() {
    if (!productoActual) {
      showAlert('Busque un producto primero.', 'warning');
      return;
    }
    var modo = modoStockActual();
    var stockPayload = leerStockParaGuardar(modo);
    if (stockPayload.error) {
      showAlert(stockPayload.error, 'warning');
      return;
    }
    var refFactura = leerRefDocumento(inpFactura);
    var refGuia = leerRefDocumento(inpGuia);
    var body = {
      producto_id: productoActual.id,
      precio_venta: (inpPrecio.value || '').trim(),
      motivo: (inpMotivo.value || '').trim(),
      modo_stock: modo,
      sector_ubicacion: (inpSector.value || '').trim(),
    };
    if (refFactura) body.numero_factura = refFactura;
    if (refGuia) body.numero_guia = refGuia;
    if (stockPayload.stock_tienda != null) body.stock_tienda = stockPayload.stock_tienda;
    if (stockPayload.stock_bodega != null) body.stock_bodega = stockPayload.stock_bodega;
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
        var nomGuardado =
          (productoActual && productoActual.nombre) ||
          (data.producto && data.producto.nombre) ||
          'Producto';
        var msg;
        if (data.sin_cambio) {
          msg = 'Sin cambios en «' + nomGuardado + '». Escanee el siguiente código.';
        } else {
          msg = 'Guardado: «' + nomGuardado + '»';
          if (data.precio_nuevo) msg += ' · SD ' + fmtCLP(data.precio_nuevo);
          if (data.stock) {
            msg += ' · Stock tienda ' + (data.stock.tienda != null ? data.stock.tienda : '—');
            msg += ' · bodega ' + (data.stock.bodega != null ? data.stock.bodega : '—');
          }
          if (data.delta_tienda || data.delta_bodega) {
            msg += ' (Δ T' + (data.delta_tienda || 0) + ' B' + (data.delta_bodega || 0) + ')';
          }
          if (data.numero_factura) msg += ' · F ' + data.numero_factura;
          if (data.numero_guia) msg += ' · G ' + data.numero_guia;
          msg += '. Escanee el siguiente código.';
        }
        persistirRefsDocumento();
        limpiarFormularioPiloto();
        showAlert(msg, data.sin_cambio ? 'info' : 'success');
        if (data.bitacora_row) prependBitacora(data.bitacora_row);
        setTimeout(prepararSiguienteEscaneo, 0);
      })
      .catch(function () {
        showAlert('Error de red al guardar.', 'danger');
      });
  }

  function iniciarPanel() {
    enlazarDom();
    if (window.PreciosPilotoBusqueda) {
      busquedaApi = window.PreciosPilotoBusqueda.init() || window.__preciosPilotoBusquedaApi;
    }
    if (!busquedaApi) {
      busquedaApi = window.__preciosPilotoBusquedaApi || null;
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

    var q0 = (new URLSearchParams(window.location.search).get('codigo') || '').trim();
    var codigoInicialEl = document.getElementById('pilotoCodigoInicial');
    if (!q0 && codigoInicialEl) {
      q0 = (codigoInicialEl.value || '').trim();
    }
    if (q0 && busquedaApi && busquedaApi.buscar) {
      var formBus = document.getElementById('formBusquedaPreciosPiloto');
      var inp = formBus ? formBus.querySelector('#posBuscarManual') : document.getElementById('posBuscarManual');
      if (inp) inp.value = q0;
      busquedaApi.buscar(q0, { autoSeleccionar: true, permitirCorto: true });
    } else if (busquedaApi && busquedaApi.prepararEscaneo) {
      setTimeout(function () {
        busquedaApi.prepararEscaneo();
      }, 50);
    }

    restaurarRefsDocumento();
    syncModoStockUi();
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', iniciarPanel);
  } else {
    iniciarPanel();
  }
})();
