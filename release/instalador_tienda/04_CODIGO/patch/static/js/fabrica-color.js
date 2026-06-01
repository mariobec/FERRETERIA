(function () {
  'use strict';

  var cfgEl = document.getElementById('fabricaColorConfig');
  if (!cfgEl) return;

  var cfg;
  try {
    cfg = JSON.parse(cfgEl.textContent || '{}');
  } catch (e) {
    return;
  }

  var initial = cfg.initial || {};
  var stockMode = initial.modo === 'stock_erp';
  var sceneUrls = cfg.scene_urls || {};
  var familiasInterior = initial.familias_interior || initial.familias || [];
  var familiasExterior = initial.familias_exterior || [];
  var lizTipTimer = null;
  var lizTipSeq = 0;
  var sceneImageCache = {};
  var sceneDrawToken = 0;
  var sceneResizeTimer = null;
  var DEFAULT_WALL_POLYGON = [[0.05, 0.08], [0.95, 0.08], [0.95, 0.55], [0.05, 0.55]];

  var state = {
    step: 1,
    ambiente_id: (initial.ambientes && initial.ambientes[0] && initial.ambientes[0].id) || 'comedor',
    color_id: (initial.defaults && initial.defaults.color_id) || (initial.colores && initial.colores[0] && initial.colores[0].id) || '',
    brillo_id: (initial.brillos && initial.brillos[0] && initial.brillos[0].id) || 'mate',
    familia_id: (initial.familias && initial.familias[0] && initial.familias[0].id) || 'blanco',
    m2: 12,
    calidad_id: 'standard',
    producto_id: null,
    cotizacion: null,
  };

  var els = {
    main: document.getElementById('fcMain'),
    pick: document.getElementById('fcPick'),
    workspace: document.getElementById('fcWorkspace'),
    changeAmbiente: document.getElementById('fcChangeAmbiente'),
    scene: document.getElementById('fcScene'),
    sceneCanvas: document.getElementById('fcSceneCanvas'),
    sceneSwatch: document.getElementById('fcSceneSwatch'),
    sceneLabel: document.getElementById('fcSceneLabel'),
    lizTip: null,
    lizTipText: null,
    cartillaCount: document.getElementById('fcCartillaCount'),
    progressFill: document.getElementById('fcProgressFill'),
    stepsNav: document.getElementById('fcStepsNav'),
    ambientes: document.getElementById('fcAmbientes'),
    familias: document.getElementById('fcFamilias'),
    paleta: document.getElementById('fcPaleta'),
    brillos: document.getElementById('fcBrillos'),
    m2: document.getElementById('fcM2'),
    cantidadResumen: document.getElementById('fcCantidadResumen'),
    calidades: document.getElementById('fcCalidades'),
    resultado: document.getElementById('fcResultado'),
    complementos: document.getElementById('fcComplementos'),
    proyectoTotal: document.getElementById('fcProyectoTotal'),
    acciones: document.getElementById('fcAcciones'),
    prev: document.getElementById('fcPrev'),
    next: document.getElementById('fcNext'),
  };

  function activeFamilias() {
    var amb = ambienteById(state.ambiente_id);
    if (amb && amb.uso === 'exterior' && familiasExterior.length) {
      return familiasExterior;
    }
    return familiasInterior.length ? familiasInterior : (initial.familias || []);
  }

  function allActiveColores() {
    var fams = activeFamilias();
    var out = [];
    fams.forEach(function (f) {
      (f.colores || []).forEach(function (c) { out.push(c); });
    });
    return out;
  }

  function colorById(id) {
    var cols = allActiveColores().concat(initial.colores || []);
    return cols.find(function (c) { return c.id === id; })
      || (initial.colores || []).find(function (c) { return c.id === id; });
  }

  function ambienteById(id) {
    return (initial.ambientes || []).find(function (a) { return a.id === id; });
  }

  function brilloById(id) {
    return (initial.brillos || []).find(function (b) { return b.id === id; });
  }

  function sceneForAmbiente(amb) {
    return (amb && amb.scene) || 'interior';
  }

  function calcLocalCantidad() {
    var m2 = parseFloat(state.m2) || 1;
    var manos = (initial.defaults && initial.defaults.manos) || 2;
    var rend = (initial.defaults && initial.defaults.rendimiento_m2_galon) || 35;
    var litrosPorGalon = (initial.defaults && initial.defaults.litros_por_galon) || 3.785;
    var litros = (m2 * manos) / rend * litrosPorGalon;
    var galones = litros / litrosPorGalon;
    var galonesCeil = Math.max(1, Math.ceil(galones * 4) / 4);
    return {
      m2: m2,
      manos: manos,
      galones_sugeridos: galonesCeil,
      galones_sugeridos_fmt: galonesCeil.toFixed(2).replace('.', ','),
    };
  }

  function pulseScene() {
    if (!els.scene) return;
    els.scene.classList.remove('is-updating');
    void els.scene.offsetWidth;
    els.scene.classList.add('is-updating');
    setTimeout(function () {
      if (els.scene) els.scene.classList.remove('is-updating');
    }, 520);
  }

  function loadSceneImage(url) {
    if (!url) return Promise.reject(new Error('no_url'));
    if (sceneImageCache[url] && sceneImageCache[url].complete && sceneImageCache[url].naturalWidth) {
      return Promise.resolve(sceneImageCache[url]);
    }
    return new Promise(function (resolve, reject) {
      var img = new Image();
      img.crossOrigin = 'anonymous';
      img.onload = function () {
        sceneImageCache[url] = img;
        resolve(img);
      };
      img.onerror = reject;
      img.src = url;
    });
  }

  function wallPolygonFor(amb) {
    if (amb && amb.wall_polygons && amb.wall_polygons[0] && amb.wall_polygons[0].length >= 3) {
      return amb.wall_polygons[0];
    }
    if (amb && amb.wall_polygon && amb.wall_polygon.length >= 3) {
      return amb.wall_polygon;
    }
    return DEFAULT_WALL_POLYGON;
  }

  function traceWallPolygon(ctx, polygon, w, h) {
    ctx.beginPath();
    polygon.forEach(function (pt, i) {
      var x = pt[0] * w;
      var y = pt[1] * h;
      if (i === 0) ctx.moveTo(x, y);
      else ctx.lineTo(x, y);
    });
    ctx.closePath();
  }

  function buildMaskFromAmbiente(w, h, amb) {
    var c = document.createElement('canvas');
    c.width = w;
    c.height = h;
    var cx = c.getContext('2d');
    cx.fillStyle = '#000000';
    cx.fillRect(0, 0, w, h);
    var polys = (amb && amb.wall_polygons) || [];
    if (!polys.length && amb && amb.wall_polygon) {
      polys = [amb.wall_polygon];
    }
    if (!polys.length) {
      polys = [DEFAULT_WALL_POLYGON];
    }
    polys.forEach(function (poly) {
      traceWallPolygon(cx, poly, w, h);
      cx.fillStyle = '#ffffff';
      cx.fill();
    });
    (amb && amb.wall_exclusions || []).forEach(function (ex) {
      cx.beginPath();
      cx.ellipse(ex[0] * w, ex[1] * h, ex[2] * w, ex[3] * h, 0, 0, Math.PI * 2);
      cx.fillStyle = '#000000';
      cx.fill();
    });
    return c;
  }

  function binarizeMaskCanvas(src, w, h) {
    var c = document.createElement('canvas');
    c.width = w;
    c.height = h;
    var cx = c.getContext('2d');
    cx.drawImage(src, 0, 0, w, h);
    var imgData = cx.getImageData(0, 0, w, h);
    var d = imgData.data;
    for (var i = 0; i < d.length; i += 4) {
      var on = d[i] > 140 || d[i + 1] > 140 || d[i + 2] > 140;
      d[i] = d[i + 1] = d[i + 2] = 255;
      d[i + 3] = on ? 255 : 0;
    }
    cx.putImageData(imgData, 0, 0);
    return c;
  }

  function resolveMask(w, h, amb, maskImg) {
    var hasPoly = amb && (
      (amb.wall_polygons && amb.wall_polygons.length) ||
      (amb.wall_polygon && amb.wall_polygon.length >= 3)
    );
    // Polígonos ERP = fuente de verdad. PNG GrabCut/IA deja manchas irregulares.
    if (hasPoly && !amb.use_mask_png) {
      return binarizeMaskCanvas(buildMaskFromAmbiente(w, h, amb), w, h);
    }
    if (maskImg && maskImg.width) {
      return binarizeMaskCanvas(maskImg, w, h);
    }
    return binarizeMaskCanvas(buildMaskFromAmbiente(w, h, amb), w, h);
  }

  function hexToRgb(hex) {
    var h = String(hex || '#888888').replace('#', '');
    if (h.length === 3) {
      h = h[0] + h[0] + h[1] + h[1] + h[2] + h[2];
    }
    return {
      r: parseInt(h.slice(0, 2), 16) || 0,
      g: parseInt(h.slice(2, 4), 16) || 0,
      b: parseInt(h.slice(4, 6), 16) || 0,
    };
  }

  function multiplyStrength(brilloId) {
    if (brilloId === 'semi_brillo') return 0.88;
    if (brilloId === 'satinado') return 0.85;
    return 0.82;
  }

  function wallTintThresholds(amb) {
    var t = (amb && amb.wall_tint) || {};
    return {
      lumMin: typeof t.lum_min === 'number' ? t.lum_min : 72,
      satMax: typeof t.sat_max === 'number' ? t.sat_max : 68,
    };
  }

  function isWallLikePixel(r, g, b, amb) {
    var th = wallTintThresholds(amb);
    var lum = (r + g + b) / 3;
    var sat = Math.max(r, g, b) - Math.min(r, g, b);
    if (lum < th.lumMin || sat > th.satMax) return false;
    return true;
  }

  function wallTintAlpha(baseAlpha, r, g, b, amb) {
    var th = wallTintThresholds(amb);
    var lum = (r + g + b) / 3;
    return baseAlpha * Math.min(1, Math.max(0, (lum - th.lumMin) / 85));
  }

  /**
   * Multiply por píxel sobre la foto ya dibujada — conserva sombras y textura del muro.
   * Con smart_wall_tint: ignora muebles oscuros y telas saturadas dentro de la máscara.
   */
  function applyWallTint(ctx, w, h, hex, brilloId, maskCanvas, amb) {
    var snap = ctx.getImageData(0, 0, w, h);
    var d = snap.data;
    var mask = maskCanvas.getContext('2d').getImageData(0, 0, w, h).data;
    var baseAlpha = multiplyStrength(brilloId);
    var smart = !amb || amb.smart_wall_tint !== false;
    var rgb = hexToRgb(hex);
    var cr = rgb.r / 255;
    var cg = rgb.g / 255;
    var cb = rgb.b / 255;

    for (var i = 0; i < d.length; i += 4) {
      if (mask[i + 3] < 128) continue;
      var pr = d[i];
      var pg = d[i + 1];
      var pb = d[i + 2];
      if (smart && !isWallLikePixel(pr, pg, pb, amb)) continue;
      var a = smart ? wallTintAlpha(baseAlpha, pr, pg, pb, amb) : baseAlpha;
      if (a <= 0) continue;
      d[i] = Math.round(pr * (1 - a) + pr * cr * a);
      d[i + 1] = Math.round(pg * (1 - a) + pg * cg * a);
      d[i + 2] = Math.round(pb * (1 - a) + pb * cb * a);
    }
    ctx.putImageData(snap, 0, 0);

    if (brilloId === 'satinado' || brilloId === 'semi_brillo') {
      var gloss = document.createElement('canvas');
      gloss.width = w;
      gloss.height = h;
      var g = gloss.getContext('2d');
      var grad = g.createLinearGradient(w * 0.45, 0, w, h * 0.42);
      grad.addColorStop(0, 'rgba(255,255,255,0)');
      grad.addColorStop(1, brilloId === 'semi_brillo' ? 'rgba(255,255,255,0.55)' : 'rgba(255,255,255,0.35)');
      g.fillStyle = grad;
      g.fillRect(0, 0, w, h);
      g.globalCompositeOperation = 'destination-in';
      g.drawImage(maskCanvas, 0, 0, w, h);
      ctx.save();
      ctx.globalCompositeOperation = 'screen';
      ctx.globalAlpha = brilloId === 'semi_brillo' ? 0.18 : 0.10;
      ctx.drawImage(gloss, 0, 0, w, h);
      ctx.restore();
      ctx.globalAlpha = 1;
    }
  }

  var sceneBuffer = null;

  function drawSceneCanvas() {
    if (!els.sceneCanvas || !els.scene) return;
    var col = colorById(state.color_id);
    var amb = ambienteById(state.ambiente_id);
    var sceneId = sceneForAmbiente(amb);
    var photoUrl = (amb && amb.photo_url) || sceneUrls[sceneId] || sceneUrls.interior || '';
    var maskUrl = (amb && amb.mask_url) || '';
    if (!photoUrl) return;

    var token = ++sceneDrawToken;
    var hex = (col && col.hex) || '#ECEFF1';
    var brilloId = state.brillo_id || 'mate';

    var loads = [loadSceneImage(photoUrl)];
    if (maskUrl) {
      loads.push(loadSceneImage(maskUrl).catch(function () { return null; }));
    } else {
      loads.push(Promise.resolve(null));
    }

    Promise.all(loads).then(function (parts) {
      if (token !== sceneDrawToken) return;
      var img = parts[0];
      var maskImg = parts[1];
      var wrap = els.sceneCanvas.parentElement;
      var cssW = Math.max(280, (wrap && wrap.clientWidth) || 640);
      var cssH = Math.round(cssW * (img.height / img.width));
      var dpr = window.devicePixelRatio || 1;
      var bufW = Math.round(cssW * dpr);
      var bufH = Math.round(cssH * dpr);
      var maskCanvas = resolveMask(cssW, cssH, amb, maskImg);

      if (!sceneBuffer) {
        sceneBuffer = document.createElement('canvas');
      }
      sceneBuffer.width = bufW;
      sceneBuffer.height = bufH;
      els.sceneCanvas.width = bufW;
      els.sceneCanvas.height = bufH;
      els.sceneCanvas.style.width = cssW + 'px';
      els.sceneCanvas.style.height = cssH + 'px';

      var bctx = sceneBuffer.getContext('2d');
      bctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      bctx.clearRect(0, 0, cssW, cssH);
      bctx.drawImage(img, 0, 0, cssW, cssH);
      applyWallTint(bctx, cssW, cssH, hex, brilloId, maskCanvas, amb);

      var ctx = els.sceneCanvas.getContext('2d');
      ctx.setTransform(1, 0, 0, 1, 0, 0);
      ctx.clearRect(0, 0, bufW, bufH);
      ctx.drawImage(sceneBuffer, 0, 0);
    }).catch(function () {
      if (token !== sceneDrawToken || !els.sceneCanvas) return;
      var ctx = els.sceneCanvas.getContext('2d');
      var w = els.sceneCanvas.clientWidth || 640;
      var h = els.sceneCanvas.clientHeight || 360;
      ctx.clearRect(0, 0, w, h);
      ctx.fillStyle = '#eceff1';
      ctx.fillRect(0, 0, w, h);
    });
  }

  function preloadAllSceneAssets() {
    var seen = {};
    (initial.ambientes || []).forEach(function (a) {
      [a.photo_url, a.mask_url].forEach(function (url) {
        if (url && !seen[url]) {
          seen[url] = true;
          loadSceneImage(url).catch(function () {});
        }
      });
    });
  }

  function scheduleSceneRedraw() {
    if (sceneResizeTimer) clearTimeout(sceneResizeTimer);
    sceneResizeTimer = setTimeout(drawSceneCanvas, 80);
  }

  function updateScene() {
    var col = colorById(state.color_id);
    var amb = ambienteById(state.ambiente_id);
    var brillo = brilloById(state.brillo_id);
    var sceneId = sceneForAmbiente(amb);

    if (els.scene) {
      els.scene.setAttribute('data-scene', sceneId);
      if (amb && amb.id) {
        els.scene.setAttribute('data-ambiente', amb.id);
      }
      els.scene.classList.add('fc-scene--canvas');
    }
    drawSceneCanvas();
    if (col) {
      document.documentElement.style.setProperty('--fc-hex', col.hex);
    }
    if (els.sceneSwatch && col) {
      els.sceneSwatch.style.backgroundColor = col.hex;
    }
    if (els.sceneLabel) {
      var parts = [];
      if (amb) parts.push(amb.nombre);
      if (col) parts.push(col.nombre);
      if (brillo) parts.push(brillo.nombre);
      els.sceneLabel.textContent = parts.join(' · ') || 'Vista previa';
    }
  }

  function lizTipForStep() {
    var amb = ambienteById(state.ambiente_id);
    var brillo = brilloById(state.brillo_id);
    var col = colorById(state.color_id);
    var m2 = parseFloat(state.m2) || 12;

    if (state.step === 1 && amb) {
      if (amb.id === 'bano') {
        return 'En baños conviene satinado o semi brillo: resisten humedad y son fáciles de limpiar.';
      }
      if (amb.id === 'fachada') {
        return 'Para fachada use pintura exterior con filtro UV. Le mostraremos opciones con stock en tienda.';
      }
      if (amb.id === 'dormitorio') {
        return 'En dormitorios, tonos suaves y acabado mate ayudan a un ambiente más relajado.';
      }
      return amb.tip || 'Elija el ambiente y verá una vista previa con el color que seleccione.';
    }

    if (state.step === 2) {
      if (amb && amb.id === 'bano' && state.brillo_id === 'mate') {
        return 'Para baño, el mate puede marcar manchas de humedad. ¿Probamos satinado? Resiste mejor el vapor.';
      }
      if (amb && amb.id === 'cocina' && state.brillo_id === 'mate') {
        return 'En cocina el satinado facilita limpiar grasa y salpicaduras sin perder elegancia.';
      }
      if (col && col.familia === 'neutro' && amb && amb.id === 'living') {
        return 'Los grises y neutros amplían visualmente el living. Combine con blanco en cielo.';
      }
      if (brillo) {
        return brillo.ideal + '. Puede cambiar el brillo y ver cómo afecta la vista previa.';
      }
    }

    if (state.step === 3) {
      if (m2 <= 10) {
        return 'Para un dormitorio pequeño (~10 m² de muro) suele alcanzar 1 galón a 2 manos.';
      }
      if (m2 >= 25) {
        return 'Superficies amplias conviene calcular con margen. Incluimos redondeo a cuartos de galón.';
      }
      var c = calcLocalCantidad();
      return 'Con ' + m2 + ' m² estimamos ' + c.galones_sugeridos_fmt + ' galones a 2 manos. Ajuste si incluye cielo.';
    }

    return '';
  }

  function renderLizTipLocal() {
    /* Tips contextuales: usar botón flotante Liz (no barra en wizard). */
  }

  function fetchLizTip() {
    /* deshabilitado en wizard — evita barra confusa; Liz sigue en esquina. */
  }

  function renderLizTip() {}

  function syncPaletaAmbiente() {
    var fams = activeFamilias();
    if (!fams.length) return;
    var ids = fams.map(function (f) { return f.id; });
    if (ids.indexOf(state.familia_id) < 0) {
      state.familia_id = fams[0].id;
    }
    var fam = fams.find(function (f) { return f.id === state.familia_id; });
    var cols = (fam && fam.colores) || [];
    if (!colorById(state.color_id) && cols[0]) {
      state.color_id = cols[0].id;
    }
  }

  function updateCartillaCount() {
    if (!els.cartillaCount) return;
    var n = allActiveColores().length;
    if (!n && initial.sin_stock) {
      els.cartillaCount.textContent = '0 — consulte en mostrador';
      return;
    }
    els.cartillaCount.textContent = String(n);
  }

  function selectAmbiente(id, advance) {
    state.ambiente_id = id;
    sceneDrawToken++;
    syncPaletaAmbiente();
    renderAmbientes();
    renderFamilias();
    renderPaleta();
    updateScene();
    pulseScene();
    renderLizTip();
    if (state.step === 4) fetchCotizacion();
    if (advance && state.step === 1) {
      setStep(2);
    }
  }

  function renderAmbientes() {
    if (!els.ambientes) return;
    els.ambientes.innerHTML = (initial.ambientes || []).map(function (a) {
      var sel = a.id === state.ambiente_id ? ' is-selected' : '';
      var hero = a.grid_class ? ' ' + a.grid_class : '';
      var photo = a.photo_url ? ' style="background-image:url(\'' + a.photo_url + '\')"' : '';
      return (
        '<button type="button" class="fc-amb-card' + hero + sel + '" data-ambiente="' + a.id + '"' + photo + '>' +
        '<span class="fc-amb-card__label">' + a.nombre + '</span>' +
        '<span class="fc-amb-card__shade"></span></button>'
      );
    }).join('');
    els.ambientes.querySelectorAll('[data-ambiente]').forEach(function (btn) {
      btn.addEventListener('click', function () {
        selectAmbiente(btn.getAttribute('data-ambiente'), true);
      });
    });
  }

  function renderFamilias() {
    if (!els.familias) return;
    var fams = activeFamilias();
    els.familias.innerHTML = fams.map(function (f) {
      var active = f.id === state.familia_id ? ' is-active' : '';
      return '<button type="button" class="fc-pill' + active + '" data-familia="' + f.id + '">' + f.nombre + '</button>';
    }).join('');
    els.familias.querySelectorAll('[data-familia]').forEach(function (btn) {
      btn.addEventListener('click', function () {
        state.familia_id = btn.getAttribute('data-familia');
        var fam = activeFamilias().find(function (f) { return f.id === state.familia_id; });
        if (fam && fam.colores && fam.colores[0]) {
          state.color_id = fam.colores[0].id;
        }
        renderFamilias();
        renderPaleta();
        updateScene();
        pulseScene();
        renderLizTip();
        if (state.step === 4) fetchCotizacion();
      });
    });
  }

  function renderPaleta() {
    if (!els.paleta) return;
    var fam = activeFamilias().find(function (f) { return f.id === state.familia_id; });
    var cols = (fam && fam.colores) || allActiveColores();
    if (!state.color_id && cols[0]) state.color_id = cols[0].id;
    els.paleta.innerHTML = cols.map(function (c) {
      var sel = c.id === state.color_id ? ' is-selected' : '';
      return (
        '<button type="button" class="fc-swatch' + sel + '" data-color="' + c.id + '" title="' + (c.nombre_completo || c.nombre) + '">' +
        '<span style="background:' + c.hex + '"></span><em>' + c.nombre + '</em>' +
        (stockMode && c.stock_tienda ? '<small class="fc-swatch-stock">' + c.stock_tienda + ' en tienda</small>' : '') +
        '<small class="fc-swatch-code">' + (c.codigo || '') + '</small></button>'
      );
    }).join('');
    els.paleta.querySelectorAll('[data-color]').forEach(function (btn) {
      btn.addEventListener('click', function () {
        state.color_id = btn.getAttribute('data-color');
        var col = colorById(state.color_id);
        if (stockMode && col && col.producto_id) {
          state.producto_id = col.producto_id;
        }
        renderPaleta();
        updateScene();
        pulseScene();
        renderLizTip();
        if (state.step === 4) fetchCotizacion();
      });
    });
  }

  function renderBrillos() {
    if (!els.brillos) return;
    els.brillos.innerHTML = (initial.brillos || []).map(function (b) {
      var sel = b.id === state.brillo_id ? ' is-selected' : '';
      return (
        '<button type="button" class="fc-card-opt' + sel + '" data-brillo="' + b.id + '">' +
        '<strong>' + b.nombre + '</strong>' +
        '<small>' + b.desc + '</small>' +
        '<small class="d-block mt-1">' + b.ideal + '</small></button>'
      );
    }).join('');
    els.brillos.querySelectorAll('[data-brillo]').forEach(function (btn) {
      btn.addEventListener('click', function () {
        state.brillo_id = btn.getAttribute('data-brillo');
        renderBrillos();
        updateScene();
        renderLizTip();
        if (state.step === 4) fetchCotizacion();
      });
    });
  }

  function renderCantidadResumen() {
    if (!els.cantidadResumen) return;
    var c = calcLocalCantidad();
    els.cantidadResumen.innerHTML =
      '<strong>' + c.galones_sugeridos_fmt + ' galones</strong> estimados para ' +
      c.m2 + ' m² · ' + c.manos + ' manos (rendimiento referencial).';
  }

  function renderCalidades() {
    if (!els.calidades) return;
    if (stockMode) {
      els.calidades.innerHTML = '';
      els.calidades.classList.add('d-none');
      return;
    }
    els.calidades.classList.remove('d-none');
    els.calidades.innerHTML = (initial.calidades || []).map(function (q) {
      var sel = q.id === state.calidad_id ? ' is-selected' : '';
      return (
        '<button type="button" class="fc-calidad-card' + sel + '" data-calidad="' + q.id + '">' +
        (q.badge ? '<span class="fc-calidad-badge">' + q.badge + '</span>' : '') +
        '<strong>' + q.nombre + '</strong></button>'
      );
    }).join('');
    els.calidades.querySelectorAll('[data-calidad]').forEach(function (btn) {
      btn.addEventListener('click', function () {
        state.calidad_id = btn.getAttribute('data-calidad');
        state.producto_id = null;
        renderCalidades();
        fetchCotizacion();
      });
    });
  }

  function buildCartLines(data) {
    var lines = [];
    var p = data.producto;
    var tot = data.totales || {};
    var galones = tot.galones || 1;
    if (p) {
      lines.push({
        producto_id: p.producto_id,
        nombre: p.nombre,
        referencia: p.referencia || '',
        precio: p.precio,
        precio_fmt: p.precio_fmt,
        imagen_url: p.imagen_url || '',
        disponible: p.disponible,
        stock_tienda: p.stock_tienda,
        cantidad: galones,
      });
    }
    (data.complementos || []).forEach(function (c) {
      if (!c.disponible) return;
      lines.push({
        producto_id: c.producto_id,
        nombre: c.nombre,
        referencia: '',
        precio: c.precio || 0,
        precio_fmt: c.precio_fmt,
        imagen_url: '',
        disponible: c.disponible,
        stock_tienda: c.stock_tienda,
        cantidad: 1,
      });
    });
    return lines;
  }

  function pedirEnCaja(data) {
    var lines = buildCartLines(data);
    if (!lines.length) return;
    if (window.tiendaCarritoReplace) {
      window.tiendaCarritoReplace(lines);
    } else if (window.tiendaCarritoAdd) {
      lines.forEach(function (ln) {
        window.tiendaCarritoAdd(ln, ln.cantidad || 1);
      });
    }
    if (window.tiendaGenerarValePedido) {
      window.tiendaGenerarValePedido();
      return;
    }
    if (window.__tiendaSetCartOpen) {
      window.__tiendaSetCartOpen(true);
    }
  }

  function renderResultado(data) {
    if (!els.resultado) return;
    if (!data || !data.ok) {
      if (els.proyectoTotal) {
        els.proyectoTotal.classList.add('d-none');
        els.proyectoTotal.innerHTML = '';
      }
      if (els.complementos) els.complementos.innerHTML = '';
      if (els.acciones) els.acciones.innerHTML = '';
      els.resultado.innerHTML = '<p class="text-muted mb-0">No pudimos cotizar. Intente otra calidad.</p>';
      return;
    }

    state.cotizacion = data;
    var p = data.producto;
    var tinte = data.tinte || {};
    var tot = data.totales || {};

    if (p) state.producto_id = p.producto_id;

    var imgBlock = p && p.imagen_url
      ? '<img src="' + p.imagen_url + '" alt="">'
      : '<div class="fc-hero-placeholder"><i class="fas fa-fill-drip fa-2x text-muted"></i></div>';

    var stockCls = p && p.disponible ? 'fc-stock-ok' : 'fc-stock-no';
    var stockTxt = p && p.disponible ? 'Disponible en tienda ahora' : 'Consultar stock en mostrador';

    var heroHtml =
      '<div class="fc-proyecto-hero">' +
      '<div class="fc-proyecto-hero__media">' + imgBlock +
      (tinte.hex ? '<span class="fc-proyecto-hero__color" style="background:' + tinte.hex + '"></span>' : '') +
      '</div>' +
      '<div class="fc-proyecto-hero__copy">' +
      '<div class="fc-proyecto-hero__kicker">Su proyecto</div>' +
      '<h3>' + data.titulo + '</h3>' +
      '<p class="fc-proyecto-hero__meta">' + data.resumen + '</p>';

    if (tinte.codigo) {
      heroHtml +=
        '<div class="fc-proyecto-hero__tinte">' +
        '<i class="fas fa-box"></i> ' + (data.modo === 'stock_erp' || tinte.modo === 'stock_erp' ? 'En stock · ' : 'Tinte ') +
        tinte.codigo + (tinte.marca ? ' · ' + tinte.marca : '') +
        '</div>';
    }

    if (p) {
      heroHtml +=
        '<div class="fw-semibold fs-5 mb-1">' + p.nombre + '</div>' +
        '<div class="mb-1">' + p.precio_fmt + ' / gal · ref. ' + (p.referencia || '—') + '</div>' +
        '<div class="' + stockCls + '">' + stockTxt + '</div>';
    } else {
      heroHtml += '<p class="text-muted mb-0">No hay pinturas en catálogo para este tier. Consulte en mostrador.</p>';
    }

    heroHtml += '</div></div>';
    els.resultado.innerHTML = heroHtml;

    if (els.proyectoTotal && tot.total_proyecto_fmt) {
      els.proyectoTotal.classList.remove('d-none');
      var compRow = tot.subtotal_complementos > 0
        ? '<div class="fc-proyecto-total__row"><span>Complementos</span><span>' + tot.subtotal_complementos_fmt + '</span></div>'
        : '';
      els.proyectoTotal.innerHTML =
        '<div class="fc-proyecto-total__row"><span>Pintura (' + (tot.galones || 1) + ' gal)</span><span>' + tot.subtotal_pintura_fmt + '</span></div>' +
        compRow +
        '<div class="fc-proyecto-total__grand"><span>Total referencial proyecto</span><em>' + tot.total_proyecto_fmt + '</em></div>' +
        '<p class="small mb-0 mt-2 opacity-75">' +
        (stockMode ? 'Stock sujeto a venta en piso. Unidades según formato del envase.' : 'Incluye tinte en mostrador. Cobro final en caja.') +
        '</p>';
    } else if (els.proyectoTotal) {
      els.proyectoTotal.classList.add('d-none');
    }

    if (els.complementos) {
      var comps = data.complementos || [];
      if (!comps.length) {
        els.complementos.innerHTML = '';
      } else {
        els.complementos.innerHTML =
          '<h3 class="h6 fw-bold mb-2">Complementos sugeridos</h3>' +
          '<div class="fc-comp-chips">' +
          comps.map(function (c) {
            var cls = c.disponible ? '' : ' is-unavailable';
            var st = c.disponible ? ' · en tienda' : ' · consultar';
            return (
              '<span class="fc-comp-chip' + cls + '">' +
              '<i class="fas fa-check-circle"></i>' +
              '<span>' + c.nombre + st + ' · ' + c.precio_fmt + '</span></span>'
            );
          }).join('') +
          '</div>';
      }
    }

    if (els.acciones) {
      var cajaBtn = '';
      if (cfg.modo_caja && p) {
        cajaBtn =
          '<button type="button" class="fc-btn fc-btn--caja" id="fcPedirCaja">' +
          '<i class="fas fa-cash-register me-1"></i> Pedir en caja</button>';
      }

      var wa = '';
      if (data.mensaje_whatsapp) {
        var waNum = (window.tiendaCarritoConfig && window.tiendaCarritoConfig.whatsapp) || '';
        if (waNum) {
          wa =
            '<a class="fc-btn fc-btn--wa" target="_blank" rel="noopener" href="https://wa.me/' +
            waNum + '?text=' + encodeURIComponent(data.mensaje_whatsapp) + '">' +
            '<i class="fab fa-whatsapp me-1"></i> WhatsApp</a>';
        }
      }

      var lizBtn = data.liz_prompt
        ? '<button type="button" class="fc-btn fc-btn--ghost" id="fcAskLiz">Preguntar a Liz</button>'
        : '';

      var cartBtn = p
        ? '<button type="button" class="fc-btn fc-btn--primary" id="fcAddCart">Agregar al carrito</button>'
        : '';

      els.acciones.className = 'fc-acciones fc-acciones--hero';
      els.acciones.innerHTML = cajaBtn + cartBtn + lizBtn + wa;

      var pedirBtn = document.getElementById('fcPedirCaja');
      if (pedirBtn) {
        pedirBtn.addEventListener('click', function () {
          pedirEnCaja(data);
        });
      }

      var addBtn = document.getElementById('fcAddCart');
      if (addBtn && p && window.tiendaCarritoAdd) {
        addBtn.addEventListener('click', function () {
          var galones = (tot.galones || 1);
          window.tiendaCarritoAdd({
            producto_id: p.producto_id,
            nombre: p.nombre,
            referencia: p.referencia || '',
            precio: p.precio,
            precio_fmt: p.precio_fmt,
            imagen_url: p.imagen_url || '',
            disponible: p.disponible,
            stock_tienda: p.stock_tienda,
          }, galones);
        });
      }

      var liz = document.getElementById('fcAskLiz');
      if (liz && data.liz_prompt) {
        liz.addEventListener('click', function () {
          var toggle = document.getElementById('tiendaAssistantToggle');
          var input = document.getElementById('tiendaAssistantInput');
          if (toggle) toggle.click();
          if (input) {
            input.value = data.liz_prompt;
            input.focus();
          }
        });
      }
    }
  }

  function fetchCotizacion() {
    if (!cfg.cotizar_url) return;
    els.resultado.innerHTML = '<p class="text-muted mb-0"><i class="fas fa-spinner fa-spin me-1"></i> Calculando proyecto…</p>';
    if (els.proyectoTotal) els.proyectoTotal.classList.add('d-none');
    if (els.complementos) els.complementos.innerHTML = '';
    if (els.acciones) els.acciones.innerHTML = '';

    fetch(cfg.cotizar_url, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        ambiente_id: state.ambiente_id,
        color_id: state.color_id,
        brillo_id: state.brillo_id,
        m2: state.m2,
        calidad_id: state.calidad_id,
        producto_id: state.producto_id,
      }),
    })
      .then(function (r) { return r.json(); })
      .then(renderResultado)
      .catch(function () {
        renderResultado(null);
      });
  }

  function setStep(n) {
    state.step = Math.max(1, Math.min(4, n));
    if (els.main) {
      els.main.setAttribute('data-step', String(state.step));
    }
    if (els.pick) {
      els.pick.classList.toggle('is-active', state.step === 1);
      if (state.step === 1) {
        els.pick.removeAttribute('hidden');
      } else {
        els.pick.setAttribute('hidden', '');
      }
    }
    if (els.workspace) {
      var showWs = state.step >= 2;
      els.workspace.classList.toggle('is-active', showWs);
      if (showWs) {
        els.workspace.removeAttribute('hidden');
      } else {
        els.workspace.setAttribute('hidden', '');
      }
    }
    document.querySelectorAll('.fc-step').forEach(function (sec) {
      sec.classList.toggle('is-active', parseInt(sec.getAttribute('data-step'), 10) === state.step);
    });
    if (els.stepsNav) {
      els.stepsNav.querySelectorAll('li').forEach(function (li) {
        var s = parseInt(li.getAttribute('data-step'), 10);
        li.classList.toggle('is-active', s === state.step);
        li.classList.toggle('is-done', s < state.step);
      });
    }
    if (els.progressFill) {
      els.progressFill.style.width = (state.step * 25) + '%';
    }
    if (els.prev) els.prev.disabled = state.step <= 1;
    if (els.next) {
      els.next.textContent = state.step >= 4 ? 'Recalcular' : 'Siguiente';
    }
    renderLizTip();
    if (state.step === 4) {
      fetchCotizacion();
    }
    if (state.step >= 2) {
      scheduleSceneRedraw();
    }
  }

  if (els.m2) {
    els.m2.addEventListener('input', function () {
      state.m2 = parseFloat(els.m2.value) || 1;
      renderCantidadResumen();
      renderLizTip();
    });
    document.querySelectorAll('[data-m2]').forEach(function (btn) {
      btn.addEventListener('click', function () {
        state.m2 = parseFloat(btn.getAttribute('data-m2')) || 12;
        els.m2.value = state.m2;
        renderCantidadResumen();
        renderLizTip();
      });
    });
  }

  if (els.changeAmbiente) {
    els.changeAmbiente.addEventListener('click', function () {
      setStep(1);
    });
  }

  if (els.prev) {
    els.prev.addEventListener('click', function () {
      setStep(state.step - 1);
    });
  }
  if (els.next) {
    els.next.addEventListener('click', function () {
      if (state.step >= 4) {
        fetchCotizacion();
        return;
      }
      if (state.step === 3) renderCantidadResumen();
      setStep(state.step + 1);
    });
  }

  syncPaletaAmbiente();
  if (stockMode && state.color_id) {
    var c0 = colorById(state.color_id);
    if (c0 && c0.producto_id) state.producto_id = c0.producto_id;
  }
  renderAmbientes();
  renderFamilias();
  renderPaleta();
  renderBrillos();
  renderCantidadResumen();
  renderCalidades();
  updateCartillaCount();
  preloadAllSceneAssets();
  updateScene();
  setStep(1);

  window.addEventListener('resize', scheduleSceneRedraw);
})();
