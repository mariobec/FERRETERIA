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
  var state = {
    step: 1,
    ambiente_id: (initial.ambientes && initial.ambientes[0] && initial.ambientes[0].id) || 'living',
    color_id: (initial.colores && initial.colores[0] && initial.colores[0].id) || '',
    brillo_id: (initial.brillos && initial.brillos[0] && initial.brillos[0].id) || 'mate',
    familia_id: (initial.familias && initial.familias[0] && initial.familias[0].id) || 'blanco',
    m2: 12,
    calidad_id: 'standard',
    producto_id: null,
    cotizacion: null,
  };

  var els = {
    sceneWall: document.getElementById('fcSceneWall'),
    sceneLabel: document.getElementById('fcSceneLabel'),
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
    acciones: document.getElementById('fcAcciones'),
    prev: document.getElementById('fcPrev'),
    next: document.getElementById('fcNext'),
  };

  function colorById(id) {
    return (initial.colores || []).find(function (c) { return c.id === id; });
  }

  function ambienteById(id) {
    return (initial.ambientes || []).find(function (a) { return a.id === id; });
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
      galones_sugeridos_fmt: galonesCeil.toFixed(2).replace('.', ','),
    };
  }

  function updateScene() {
    var col = colorById(state.color_id);
    var amb = ambienteById(state.ambiente_id);
    if (els.sceneWall && col) {
      els.sceneWall.style.backgroundColor = col.hex;
      document.documentElement.style.setProperty('--fc-hex', col.hex);
    }
    if (els.sceneLabel) {
      var parts = [];
      if (amb) parts.push(amb.nombre);
      if (col) parts.push(col.nombre);
      els.sceneLabel.textContent = parts.join(' · ') || 'Vista previa';
    }
  }

  function renderAmbientes() {
    if (!els.ambientes) return;
    els.ambientes.innerHTML = (initial.ambientes || []).map(function (a) {
      var sel = a.id === state.ambiente_id ? ' is-selected' : '';
      return (
        '<button type="button" class="fc-card-opt' + sel + '" data-ambiente="' + a.id + '">' +
        '<i class="fas ' + a.icono + '"></i>' +
        '<strong>' + a.nombre + '</strong>' +
        '<small>' + a.tip + '</small></button>'
      );
    }).join('');
    els.ambientes.querySelectorAll('[data-ambiente]').forEach(function (btn) {
      btn.addEventListener('click', function () {
        state.ambiente_id = btn.getAttribute('data-ambiente');
        renderAmbientes();
        updateScene();
        if (state.step === 4) fetchCotizacion();
      });
    });
  }

  function renderFamilias() {
    if (!els.familias) return;
    els.familias.innerHTML = (initial.familias || []).map(function (f) {
      var active = f.id === state.familia_id ? ' is-active' : '';
      return '<button type="button" class="fc-pill' + active + '" data-familia="' + f.id + '">' + f.nombre + '</button>';
    }).join('');
    els.familias.querySelectorAll('[data-familia]').forEach(function (btn) {
      btn.addEventListener('click', function () {
        state.familia_id = btn.getAttribute('data-familia');
        var fam = (initial.familias || []).find(function (f) { return f.id === state.familia_id; });
        if (fam && fam.colores && fam.colores[0]) {
          state.color_id = fam.colores[0].id;
        }
        renderFamilias();
        renderPaleta();
        updateScene();
        if (state.step === 4) fetchCotizacion();
      });
    });
  }

  function renderPaleta() {
    if (!els.paleta) return;
    var fam = (initial.familias || []).find(function (f) { return f.id === state.familia_id; });
    var cols = (fam && fam.colores) || initial.colores || [];
    if (!state.color_id && cols[0]) state.color_id = cols[0].id;
    els.paleta.innerHTML = cols.map(function (c) {
      var sel = c.id === state.color_id ? ' is-selected' : '';
      return (
        '<button type="button" class="fc-swatch' + sel + '" data-color="' + c.id + '" title="' + c.codigo + ' ' + c.nombre + '">' +
        '<span style="background:' + c.hex + '"></span><em>' + c.nombre + '</em></button>'
      );
    }).join('');
    els.paleta.querySelectorAll('[data-color]').forEach(function (btn) {
      btn.addEventListener('click', function () {
        state.color_id = btn.getAttribute('data-color');
        renderPaleta();
        updateScene();
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

  function renderResultado(data) {
    if (!els.resultado) return;
    if (!data || !data.ok) {
      els.resultado.innerHTML = '<p class="text-muted mb-0">No pudimos cotizar. Intente otra calidad.</p>';
      return;
    }
    state.cotizacion = data;
    var p = data.producto;
    var html = '<p class="mb-2"><strong>' + data.titulo + '</strong><br><span class="text-muted small">' + data.resumen + '</span></p>';
    if (p) {
      state.producto_id = p.producto_id;
      var img = p.imagen_url
        ? '<img src="' + p.imagen_url + '" alt="">'
        : '<div style="width:72px;height:72px;background:#eee;border-radius:8px"></div>';
      var stockCls = p.disponible ? 'fc-stock-ok' : 'fc-stock-no';
      var stockTxt = p.disponible ? 'Disponible en tienda' : 'Sin stock en tienda';
      html +=
        '<div class="fc-producto-row">' + img +
        '<div><div class="fw-semibold">' + p.nombre + '</div>' +
        '<div>' + p.precio_fmt + ' · ref ' + (p.referencia || '') + '</div>' +
        '<div class="' + stockCls + '">' + stockTxt + '</div></div></div>';
    } else {
      html += '<p class="text-muted">No hay pinturas en catálogo para este tier. Consulte en mostrador.</p>';
    }
    els.resultado.innerHTML = html;

    if (els.complementos) {
      var comps = data.complementos || [];
      if (!comps.length) {
        els.complementos.innerHTML = '';
      } else {
        els.complementos.innerHTML =
          '<h3>Complementos sugeridos</h3><ul>' +
          comps.map(function (c) {
            var st = c.disponible ? ' · stock tienda' : ' · consultar';
            return '<li><span>' + c.nombre + '</span><span>' + c.precio_fmt + st + '</span></li>';
          }).join('') +
          '</ul>';
      }
    }

    if (els.acciones) {
      var wa = '';
      if (data.mensaje_whatsapp) {
        var waNum = (window.tiendaCarritoConfig && window.tiendaCarritoConfig.whatsapp) || '';
        if (waNum) {
          wa =
            '<a class="fc-btn fc-btn--wa" target="_blank" rel="noopener" href="https://wa.me/' +
            waNum + '?text=' + encodeURIComponent(data.mensaje_whatsapp) + '">' +
            '<i class="fab fa-whatsapp me-1"></i> Enviar cotización</a>';
        }
      }
      var lizBtn = data.liz_prompt
        ? '<button type="button" class="fc-btn fc-btn--ghost" id="fcAskLiz">Preguntar a Liz</button>'
        : '';
      var cartBtn = p
        ? '<button type="button" class="fc-btn fc-btn--primary" id="fcAddCart">Agregar pintura al carrito</button>'
        : '';
      els.acciones.innerHTML = cartBtn + lizBtn + wa;

      var addBtn = document.getElementById('fcAddCart');
      if (addBtn && p && window.tiendaCarritoAdd) {
        addBtn.addEventListener('click', function () {
          window.tiendaCarritoAdd({
            producto_id: p.producto_id,
            nombre: p.nombre,
            referencia: p.referencia || '',
            precio: p.precio,
            precio_fmt: p.precio_fmt,
            imagen_url: p.imagen_url || '',
            disponible: p.disponible,
            stock_tienda: p.stock_tienda,
          });
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
    els.resultado.innerHTML = '<p class="text-muted mb-0">Calculando…</p>';
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
      els.next.textContent = state.step >= 4 ? 'Finalizar' : 'Siguiente';
    }
    if (state.step === 4) {
      fetchCotizacion();
    }
  }

  if (els.m2) {
    els.m2.addEventListener('input', function () {
      state.m2 = parseFloat(els.m2.value) || 1;
      renderCantidadResumen();
    });
    document.querySelectorAll('[data-m2]').forEach(function (btn) {
      btn.addEventListener('click', function () {
        state.m2 = parseFloat(btn.getAttribute('data-m2')) || 12;
        els.m2.value = state.m2;
        renderCantidadResumen();
      });
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

  renderAmbientes();
  renderFamilias();
  renderPaleta();
  renderBrillos();
  renderCantidadResumen();
  renderCalidades();
  updateScene();
  setStep(1);
})();
