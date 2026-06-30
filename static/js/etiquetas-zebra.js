(function () {
  'use strict';

  var ctx = window.ZEBRA_ETIQUETAS_CTX || {};
  var form = document.getElementById('formZebraConfig');
  var zplOut = document.getElementById('zebraZplOut');
  var previewBox = document.getElementById('zebraPreviewBox');
  var previewMeta = document.getElementById('zebraPreviewMeta');
  var selPerfil = document.getElementById('zebraPerfil');
  var inpLayout = document.getElementById('zebraLayout');
  var zplActual = (zplOut && zplOut.textContent) ? zplOut.textContent.trim() : '';

  function asegurarImpresoraZebraEnCampo() {
    var inp = document.getElementById('zebraImpresora');
    var pick = document.getElementById('zebraImpresoraPick');
    if (!inp) return;
    var def = (ctx.impresoraDefault || '').trim();
    if (!String(inp.value || '').trim() && def) {
      inp.value = def;
    }
    if (pick) {
      pick.addEventListener('change', function () {
        if (pick.value) inp.value = pick.value;
      });
      if (!String(inp.value || '').trim() && pick.value) {
        inp.value = pick.value;
      }
      Array.prototype.slice.call(pick.options).forEach(function (opt) {
        if (opt.value && opt.value === inp.value.trim()) {
          pick.value = opt.value;
        }
      });
    }
  }
  asegurarImpresoraZebraEnCampo();

  function impresoraDesdeForm(cfg) {
    var nom = String((cfg && cfg.impresora_nombre) || '').trim();
    if (!nom) nom = String(ctx.impresoraDefault || '').trim();
    var pick = document.getElementById('zebraImpresoraPick');
    if (!nom && pick && pick.value) nom = pick.value.trim();
    if (nom) cfg.impresora_nombre = nom;
    return cfg;
  }

  var PERFIL_PRESETS = {
    gx420d: {
      layout: 'simple',
      ancho_mm: 50,
      ancho_papel_mm: 50,
      alto_mm: 30,
      columna_ancho_mm: 40,
      columna_gap_mm: 4,
      nombre_font: 22,
      precio_font: 28,
      barcode_altura_mm: 10
    },
    gx420d_doble: {
      layout: 'doble_columna',
      ancho_mm: 85,
      ancho_papel_mm: 85,
      alto_mm: 30,
      columna_ancho_mm: 40,
      columna_gap_mm: 4,
      nombre_font: 20,
      precio_font: 24,
      barcode_modulo: 1,
      barcode_altura_mm: 8
    }
  };

  function esDoble(cfg) {
    return (cfg.layout || '').toLowerCase() === 'doble_columna' || cfg.perfil === 'gx420d_doble';
  }

  function aplicarPresetPerfil(perfil) {
    var p = PERFIL_PRESETS[perfil] || PERFIL_PRESETS.gx420d;
    if (!form) return;
    Object.keys(p).forEach(function (k) {
      var el = form.elements.namedItem(k);
      if (el) el.value = p[k];
    });
    if (inpLayout) inpLayout.value = p.layout;
    toggleCamposDoble(p.layout === 'doble_columna');
  }

  function toggleCamposDoble(doble) {
    document.querySelectorAll('.zebra-field-doble-only').forEach(function (el) {
      el.classList.toggle('d-none', !doble);
    });
    document.querySelectorAll('.zebra-field-simple-only').forEach(function (el) {
      el.classList.toggle('d-none', doble);
    });
    var hint = document.getElementById('zebraDobleHint');
    if (hint) hint.classList.toggle('d-none', !doble);
    var lbl = document.getElementById('lblAnchoPapel');
    if (lbl) lbl.textContent = doble ? 'Ancho papel total (mm)' : 'Ancho etiqueta (mm)';
  }

  function cfgDesdeForm() {
    var fd = new FormData(form);
    var cfg = {};
    fd.forEach(function (v, k) {
      if (k.indexOf('mostrar_') === 0) {
        cfg[k] = true;
        return;
      }
      if (k === 'perfil' || k === 'layout' || k === 'impresora_nombre') {
        cfg[k] = String(v);
        return;
      }
      var num = parseFloat(v);
      cfg[k] = isNaN(num) ? v : num;
    });
    ['mostrar_codigo_texto', 'mostrar_precio_lista', 'mostrar_precio_mayoreo'].forEach(function (k) {
      if (!fd.get(k)) cfg[k] = false;
    });
    if (!cfg.layout && cfg.perfil === 'gx420d_doble') cfg.layout = 'doble_columna';
    if (!cfg.perfil) cfg.perfil = selPerfil ? selPerfil.value : 'gx420d';
    if (esDoble(cfg)) {
      cfg.ancho_mm = cfg.ancho_papel_mm || cfg.ancho_mm || 85;
    }
    return impresoraDesdeForm(cfg);
  }

  function payloadBase(filasOverride) {
    return {
      variante: ctx.variante || 'catalogo',
      filas: filasOverride || ctx.filas || [],
      config: cfgDesdeForm()
    };
  }

  function filasPrueba() {
    var cfg = cfgDesdeForm();
    if (esDoble(cfg)) {
      return [
        { nombre: 'PRUEBA COL 1 LhexIA', codigo: '1111111111111', precio_clp: 1990, precio_pos: 1990, cantidad: 1 },
        { nombre: 'PRUEBA COL 2 LhexIA', codigo: '2222222222222', precio_clp: 2990, precio_pos: 2990, cantidad: 1 }
      ];
    }
    return [{
      nombre: 'Etiqueta prueba LhexIA Zebra',
      codigo: '7805201592032',
      precio_clp: 1990,
      precio_pos: 1990,
      precio_lista: 2490,
      precio_mayoreo: 1650,
      cantidad: 1
    }];
  }

  function postJson(url, body) {
    return fetch(url, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'X-Requested-With': 'XMLHttpRequest' },
      body: JSON.stringify(body || {})
    }).then(function (r) { return r.json(); });
  }

  function zplPrimeraEtiqueta(zpl) {
    if (!zpl) return '';
    var m = zpl.match(/\^XA[\s\S]*?\^XZ/);
    if (m) return m[0];
    return zpl.length > 12000 ? zpl.slice(0, 12000) : zpl;
  }

  function labelaryUrl(cfg, index) {
    var wMm = esDoble(cfg) ? (parseFloat(cfg.ancho_papel_mm) || 85) : (parseFloat(cfg.ancho_mm) || 50);
    var hMm = parseFloat(cfg.alto_mm) || 30;
    var wIn = wMm / 25.4;
    var hIn = hMm / 25.4;
    var dpmm = Math.round((parseInt(cfg.dpi, 10) || 203) / 25.4);
    if (dpmm < 6) dpmm = 8;
    return 'https://api.labelary.com/v1/printers/' + dpmm + 'dpmm/labels/' +
      wIn.toFixed(2) + 'x' + hIn.toFixed(2) + '/' + (index || 0) + '/';
  }

  function renderPreview(zpl, cfg) {
    if (!zpl) {
      previewBox.innerHTML = '<span class="text-muted small">Sin ZPL</span>';
      return;
    }
    var zplPreview = zplPrimeraEtiqueta(zpl);
    previewBox.innerHTML = '<span class="text-muted small">Generando vista previa…</span>';
    var wMm = esDoble(cfg) ? (cfg.ancho_papel_mm || 85) : (cfg.ancho_mm || 50);
    var totalBloques = (zpl.match(/\^XA/g) || []).length;
    previewMeta.textContent = wMm + '×' + (cfg.alto_mm || 30) + ' mm' +
      (esDoble(cfg) ? ' · doble' : '') +
      (totalBloques > 1 ? ' · muestra 1/' + totalBloques : '');
    fetch(labelaryUrl(cfg, 0), {
      method: 'POST',
      headers: { 'Content-Type': 'application/x-www-form-urlencoded', 'Accept': 'image/png' },
      body: zplPreview
    }).then(function (res) {
      if (!res.ok) throw new Error('Labelary ' + res.status);
      return res.blob();
    }).then(function (blob) {
      var url = URL.createObjectURL(blob);
      previewBox.innerHTML = '<img src="' + url + '" alt="Vista previa etiqueta Zebra">';
    }).catch(function (err) {
      previewBox.innerHTML = '<span class="text-danger small">No se pudo previsualizar: ' + err.message + '</span>';
    });
  }

  function refrescarZpl(imprimir, filasOverride) {
    var body = payloadBase(filasOverride);
    return postJson(ctx.previewUrl, body).then(function (data) {
      if (!data.ok) throw new Error(data.mensaje || 'Error ZPL');
      zplActual = data.zpl || '';
      if (zplOut) zplOut.textContent = zplActual;
      renderPreview(zplActual, body.config);
      if (imprimir) {
        return postJson(ctx.printUrl, {
          zpl: zplActual,
          config: body.config,
          impresora: body.config.impresora_nombre || ''
        });
      }
      return data;
    });
  }

  if (selPerfil) {
    selPerfil.addEventListener('change', function () {
      aplicarPresetPerfil(selPerfil.value);
    });
    toggleCamposDoble(esDoble(cfgDesdeForm()));
  }

  document.getElementById('btnZebraPreview').addEventListener('click', function () {
    refrescarZpl(false).catch(function (e) { alert(e.message || e); });
  });

  document.getElementById('btnZebraGuardar').addEventListener('click', function () {
    postJson(ctx.configUrl, { config: cfgDesdeForm() }).then(function (data) {
      if (!data.ok) throw new Error(data.mensaje || 'No se guardó');
      alert('Calibración guardada en data/zebra_etiqueta_config.json');
    }).catch(function (e) { alert(e.message || e); });
  });

  function imprimirPrueba(filas) {
    var cfg = cfgDesdeForm();
    postJson(ctx.previewUrl, {
      variante: ctx.variante || 'catalogo',
      filas: filas,
      config: cfg
    }).then(function (data) {
      if (!data.ok) throw new Error(data.mensaje || 'Error');
      return postJson(ctx.printUrl, { zpl: data.zpl, config: cfg, impresora: cfg.impresora_nombre || '' });
    }).then(function (res) {
      if (!res.ok) throw new Error(res.mensaje || 'Impresión falló');
      var msg = 'Etiqueta enviada a: ' + (res.impresora || 'Zebra');
      if (res.advertencia) msg += '\n\nAviso: ' + res.advertencia;
      msg += '\n(No usa la térmica 80 mm de tickets POS.)';
      alert(msg);
    }).catch(function (e) { alert(e.message || e); });
  }

  document.getElementById('btnZebraImprimir').addEventListener('click', function () {
    imprimirPrueba(filasPrueba());
  });

  document.getElementById('btnZebraImprimirLote').addEventListener('click', function () {
    refrescarZpl(true).then(function (res) {
      if (res && res.ok) {
        var msg = 'Lote enviado a: ' + (res.impresora || 'Zebra');
        if (res.advertencia) msg += '\n\nAviso: ' + res.advertencia;
        msg += '\n(No usa la térmica 80 mm de tickets POS.)';
        alert(msg);
      }
    }).catch(function (e) { alert(e.message || e); });
  });

  document.getElementById('btnZebraDescargar').addEventListener('click', function () {
    refrescarZpl(false).then(function () {
      var blob = new Blob([zplActual], { type: 'text/plain;charset=utf-8' });
      var a = document.createElement('a');
      a.href = URL.createObjectURL(blob);
      a.download = 'etiquetas_lhexia.zpl';
      a.click();
    }).catch(function (e) { alert(e.message || e); });
  });

  if (zplActual) {
    renderPreview(zplActual, cfgDesdeForm());
  }
})();
