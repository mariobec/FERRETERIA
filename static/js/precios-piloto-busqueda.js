/**
 * Carga precios piloto — buscador igual que POS (tarjetas, filtros, pistola).
 * Dispara window event 'piloto:producto-seleccionado' con { producto } al elegir ítem.
 */
(function () {
  var BUSCAR_URL = "/api/precios/piloto/buscar";
  var PRODUCTO_URL = "/api/precios/piloto/producto/";

  function escapeHtml(s) {
    return String(s || "")
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  function formatoCLP(valor) {
    return new Intl.NumberFormat("es-CL", { style: "currency", currency: "CLP" }).format(valor);
  }

  function pareceCodigoBarras(q) {
    var s = (q || "").trim();
    if (!s || s.length > 60) return false;
    return !/\s/.test(s);
  }

  function filtroActual() {
    var hid = document.getElementById("posFiltroBusqueda");
    var v = hid ? String(hid.value || "").trim().toLowerCase() : "";
    if (v === "operativo" || v === "tienda" || v === "catalogo") return v;
    return "operativo";
  }

  function setFiltro(modo) {
    var hid = document.getElementById("posFiltroBusqueda");
    if (hid) hid.value = modo;
    document.querySelectorAll(".pos-filter-pill[data-filter]").forEach(function (btn) {
      var f = (btn.getAttribute("data-filter") || "").trim();
      btn.classList.toggle("pos-filter-pill--active", f === modo);
    });
  }

  function initFiltros(onRefetch) {
    var bOp = document.getElementById("posBtnFiltroOperativo");
    var bTi = document.getElementById("posBtnFiltroTienda");
    var bCat = document.getElementById("posBtnFiltroCatalogo");
    function aplicar(modo) {
      setFiltro(modo);
      var inp = document.getElementById("posBuscarManual");
      var q = inp ? String(inp.value || "").trim() : "";
      if (q.length >= 2 && onRefetch) onRefetch(q);
      else if (onRefetch && onRefetch.hidePanel) onRefetch.hidePanel();
    }
    if (bOp) bOp.addEventListener("click", function () { aplicar("operativo"); });
    if (bTi) bTi.addEventListener("click", function () { aplicar("tienda"); });
    if (bCat) bCat.addEventListener("click", function () { aplicar("catalogo"); });
    setFiltro(filtroActual());
  }

  function initBusqueda() {
    var panel = document.getElementById("pos-search-suggestions");
    var input = document.getElementById("posBuscarManual");
    var hero = document.querySelector(".pos-unified-search-hero");
    if (!panel || !input) return null;

    var activeIndex = -1;
    var lastItems = [];
    var debounceTimer = null;
    var fetchCtrl = null;

    function setSuggestOpen(open) {
      if (!hero) return;
      hero.classList.toggle("pos-unified-search-hero--suggest-open", !!open);
    }

    function hidePanel() {
      panel.classList.add("d-none");
      panel.innerHTML = "";
      activeIndex = -1;
      lastItems = [];
      setSuggestOpen(false);
    }

    function badgeClass(tipo) {
      var t = String(tipo || "").toLowerCase();
      if (t === "economica" || t === "premium" || t === "verde" || t === "amarillo" || t === "azul" || t === "tienda" || t === "bodega" || t === "sin_stock") {
        return "pos-search-badge pos-search-badge--" + t;
      }
      return "pos-search-badge";
    }

    function semaforoCardClass(it) {
      var s = String((it && it.semaforo) || "").toLowerCase();
      if (s === "verde" || s === "amarillo" || s === "azul") return " pos-search-card--semaforo-" + s;
      return "";
    }

    function semaforoChipHtml(it) {
      var s = String((it && it.semaforo) || "verde").toLowerCase();
      var txt = s === "amarillo" ? "Bodega" : s === "azul" ? "A pedido" : "Tienda";
      if (s === "azul" && it && it.dias_entrega_estimado) txt = "A pedido ~" + String(it.dias_entrega_estimado) + "d";
      return (
        '<span class="pos-search-card__sem-chip pos-search-card__sem-chip--' + s + '">' +
        '<span class="pos-search-card__sem-dot" aria-hidden="true"></span>' +
        escapeHtml(txt) + "</span>"
      );
    }

    function itemSinStock(it) {
      if (it && String(it.semaforo || "").toLowerCase() === "azul") return true;
      if (it && it.sin_stock === true) return true;
      var st = Number(it.stock_tienda || 0);
      var sb = Number(it.stock_bodega || 0);
      var tot = Number(it.stock_total != null ? it.stock_total : st + sb);
      return tot <= 0;
    }

    function precioFmtLista(it) {
      var p = Number(it.precio);
      if (!isNaN(p) && p > 0) return formatoCLP(Math.round(p));
      if (it.precio_lista_fmt) return "Sin SD · ref. " + String(it.precio_lista_fmt);
      if (it.precio_fmt && it.precio_fmt !== "Sin precio SD") return String(it.precio_fmt);
      return "Sin precio SD";
    }

    function precioEtiquetaBusqueda(it) {
      var p = Number(it.precio);
      if (it.sin_precio_sd || !p || p <= 0) return "SIN PRECIO SD";
      return "P. VENTA SD";
    }

    function stockLinea(it) {
      var u = escapeHtml(it.unidad || "un");
      var st = Number(it.stock_tienda || 0);
      var sb = Number(it.stock_bodega || 0);
      var tot = Number(it.stock_total != null ? it.stock_total : st + sb);
      var agotado = itemSinStock(it);
      var cls = agotado ? " pos-search-card__stock--agotado" : "";
      var chip = semaforoChipHtml(it);
      var sep = '<span class="pos-search-card__stock-sep" aria-hidden="true">·</span>';
      var body = "";
      if (st > 0 && sb > 0) body = "Stock: <strong>" + tot + " " + u + "</strong> (Tienda: " + st + " / Bodega: " + sb + ")";
      else if (st > 0) body = "Stock: <strong>" + st + " " + u + "</strong> (Tienda)";
      else if (sb > 0) body = "Stock: <strong>" + sb + " " + u + "</strong> (Bodega)";
      else body = "Sin stock en tienda ni bodega · <strong>0</strong> " + u;
      return chip + sep + '<span class="' + cls.trim() + '">' + body + "</span>";
    }

    function searchThumbHtml(it) {
      var img = String((it && it.imagen_url) || "").trim();
      if (img) {
        return (
          '<div class="pos-search-card__thumb">' +
          '<img class="pos-search-card__thumb" src="' + escapeHtml(img) + '" alt="" loading="lazy" decoding="async" referrerpolicy="no-referrer"' +
          ' onerror="this.parentElement.classList.add(\'pos-search-card__thumb--empty\'); this.remove();">' +
          "</div>"
        );
      }
      return '<div class="pos-search-card__thumb pos-search-card__thumb--empty" aria-hidden="true"><i class="fas fa-box"></i></div>';
    }

    function leyendaSemaforoHtml() {
      return (
        '<div class="pos-semaforo-leyenda" aria-hidden="true">' +
        '<span class="pos-semaforo-leyenda__item pos-semaforo-leyenda__item--verde"><i></i> Tienda</span>' +
        '<span class="pos-semaforo-leyenda__item pos-semaforo-leyenda__item--amarillo"><i></i> Bodega</span>' +
        '<span class="pos-semaforo-leyenda__item pos-semaforo-leyenda__item--azul"><i></i> A pedido</span>' +
        "</div>"
      );
    }

    function indicePrimeroConStock(items) {
      for (var i = 0; i < items.length; i++) {
        var s = String(items[i].semaforo || "").toLowerCase();
        if (s === "verde" || s === "amarillo") return i;
      }
      return items.length ? 0 : -1;
    }

    function mensajeSinCoincidencias(data) {
      var filtro = filtroActual();
      var filtroLabel = filtro === "tienda" ? "Solo tienda" : filtro === "catalogo" ? "Catálogo" : "Operativo";
      var msg = "Sin coincidencias en modo <strong>" + escapeHtml(filtroLabel) + "</strong>. Pruebe otro término";
      if (filtro !== "catalogo") msg += " o pulse <strong>Catálogo</strong>";
      msg += ".";
      if (data && data.meta && data.meta.filtrados_por_stock) {
        msg += " Hay productos en catálogo sin stock en mostrador; use <strong>Catálogo</strong>.";
      }
      return msg;
    }

    function cargarProducto(productoId) {
      return fetch(PRODUCTO_URL + encodeURIComponent(String(productoId)), {
        credentials: "same-origin",
        headers: { Accept: "application/json", "X-Requested-With": "XMLHttpRequest" },
      })
        .then(function (r) {
          if (!r.ok) throw new Error("http_" + r.status);
          return r.json();
        })
        .then(function (data) {
          if (!data.ok || !data.producto) throw new Error("not_found");
          window.dispatchEvent(new CustomEvent("piloto:producto-seleccionado", { detail: { producto: data.producto } }));
          input.value = "";
          hidePanel();
          input.focus();
        });
    }

    function seleccionarItem(idx) {
      var it = lastItems[idx];
      if (!it || it.producto_id == null) return;
      cargarProducto(it.producto_id).catch(function () {
        window.dispatchEvent(
          new CustomEvent("piloto:busqueda-error", { detail: { message: "No se pudo cargar el producto." } })
        );
      });
    }

    function marcarActivo() {
      panel.querySelectorAll(".pos-search-card").forEach(function (el, i) {
        el.classList.toggle("is-active", i === activeIndex);
        el.setAttribute("aria-selected", i === activeIndex ? "true" : "false");
      });
      var active = panel.querySelector(".pos-search-card.is-active");
      if (active && active.scrollIntoView) active.scrollIntoView({ block: "nearest" });
    }

    function renderItems(items, searchMeta) {
      if (!items.length) {
        panel.innerHTML =
          '<div class="pos-search-suggestions__head">Asistente de precios</div>' +
          '<div class="pos-search-suggestions__empty">' +
          (searchMeta ? mensajeSinCoincidencias(searchMeta) : "Sin coincidencias.") +
          "</div>";
        panel.classList.remove("d-none");
        setSuggestOpen(true);
        return;
      }
      var html = items
        .map(function (it, idx) {
          var badges = (it.badges || [])
            .map(function (b) {
              return '<span class="' + badgeClass(b.tipo) + '">' + escapeHtml(b.label || "") + "</span>";
            })
            .join("");
          var marca = (it.marca || "").trim();
          var meta = "SKU: " + escapeHtml(it.codigo || "") + (marca ? " · Marca: " + escapeHtml(marca) : "");
          var sinStock = itemSinStock(it);
          return (
            '<article class="pos-search-card pos-search-card--premium' +
            semaforoCardClass(it) +
            (sinStock ? " pos-search-card--sin-stock" : "") +
            (idx === activeIndex ? " is-active" : "") +
            '" role="option" data-idx="' + idx + '" data-producto-id="' + escapeHtml(it.producto_id) + '">' +
            searchThumbHtml(it) +
            '<div class="pos-search-card__main">' +
            '<p class="pos-search-card__title">' + escapeHtml(it.nombre || it.text || "") + "</p>" +
            '<p class="pos-search-card__meta">' + meta + "</p>" +
            '<p class="pos-search-card__stock">' + stockLinea(it) + "</p>" +
            "</div>" +
            '<div class="pos-search-card__right">' +
            '<div class="pos-search-card__price-label">' + escapeHtml(precioEtiquetaBusqueda(it)) + "</div>" +
            '<div class="pos-search-card__price">' + escapeHtml(precioFmtLista(it)) + "</div>" +
            (badges ? '<div class="pos-search-card__badges">' + badges + "</div>" : "") +
            '<div class="pos-search-card__add"><i class="fas fa-tag"></i> Cargar precio</div>' +
            "</div></article>"
          );
        })
        .join("");
      panel.innerHTML =
        '<div class="pos-search-suggestions__head">Asistente de precios · ' +
        items.length +
        " resultado" +
        (items.length === 1 ? "" : "s") +
        "</div>" +
        leyendaSemaforoHtml() +
        html;
      panel.classList.remove("d-none");
      setSuggestOpen(true);
      panel.querySelectorAll(".pos-search-card").forEach(function (card) {
        card.addEventListener("mousedown", function (e) {
          e.preventDefault();
          var idx = parseInt(card.getAttribute("data-idx"), 10);
          if (!isNaN(idx)) seleccionarItem(idx);
        });
      });
    }

    function parseResponse(r) {
      if (r.status === 401 || r.status === 403) throw new Error("sesion");
      if (!r.ok) throw new Error("http_" + r.status);
      return r.json();
    }

    function ejecutarBusqueda(term, opts) {
      var q = (term || "").trim();
      opts = opts || {};
      if (q.length < 2 && !opts.permitirCorto) {
        hidePanel();
        return Promise.resolve(null);
      }
      if (fetchCtrl) fetchCtrl.abort();
      fetchCtrl = new AbortController();
      if (!opts.silencioso) {
        panel.innerHTML =
          '<div class="pos-search-suggestions__head">Asistente de precios</div>' +
          '<div class="pos-search-suggestions__loading"><i class="fas fa-spinner fa-spin me-1"></i> Buscando…</div>';
        panel.classList.remove("d-none");
        setSuggestOpen(true);
      }
      var params = new URLSearchParams({
        q: q,
        origen: "precios_piloto",
        enriquecido: "1",
        filtro_pos: filtroActual(),
      });
      return fetch(BUSCAR_URL + "?" + params.toString(), {
        credentials: "same-origin",
        headers: { Accept: "application/json", "X-Requested-With": "XMLHttpRequest" },
        signal: fetchCtrl.signal,
      })
        .then(parseResponse)
        .then(function (data) {
          lastItems = data && Array.isArray(data.results) ? data.results : [];
          activeIndex = indicePrimeroConStock(lastItems);
          if (opts.autoSeleccionar && lastItems.length === 1) {
            return seleccionarItem(0);
          }
          if (opts.autoSeleccionar && data && data.meta && data.meta.match === "codigo_exacto" && lastItems.length) {
            return seleccionarItem(0);
          }
          renderItems(lastItems, data);
          return data;
        })
        .catch(function (err) {
          if (err && err.name === "AbortError") return null;
          var msg = "No se pudo cargar la búsqueda.";
          if (err && err.message === "sesion") msg = "Sesión expirada. Recargue la página.";
          panel.innerHTML =
            '<div class="pos-search-suggestions__head">Asistente de precios</div>' +
            '<div class="pos-search-suggestions__empty">' + escapeHtml(msg) + "</div>";
          panel.classList.remove("d-none");
          setSuggestOpen(true);
          return null;
        });
    }

    function onInputKeydown(e) {
      if (e.key === "Escape") {
        if (!panel.classList.contains("d-none")) {
          e.preventDefault();
          hidePanel();
        }
        return;
      }
      if (panel.classList.contains("d-none") || !lastItems.length) {
        if (e.key === "Enter") {
          var q = (input.value || "").trim();
          e.preventDefault();
          if (pareceCodigoBarras(q)) {
            ejecutarBusqueda(q, { autoSeleccionar: true, permitirCorto: q.length >= 1 });
            return;
          }
          if (q.length >= 2) ejecutarBusqueda(q);
        }
        return;
      }
      if (e.key === "ArrowDown") {
        e.preventDefault();
        activeIndex = Math.min(lastItems.length - 1, activeIndex + 1);
        marcarActivo();
      } else if (e.key === "ArrowUp") {
        e.preventDefault();
        activeIndex = Math.max(0, activeIndex - 1);
        marcarActivo();
      } else if (e.key === "Enter") {
        e.preventDefault();
        if (activeIndex >= 0) seleccionarItem(activeIndex);
      }
    }

    input.addEventListener("input", function () {
      clearTimeout(debounceTimer);
      var term = (input.value || "").trim();
      if (term.length < 2) {
        hidePanel();
        return;
      }
      debounceTimer = setTimeout(function () {
        ejecutarBusqueda(term);
      }, 280);
    });

    input.addEventListener("keydown", onInputKeydown);

    document.addEventListener("click", function (e) {
      if (!hero) return;
      if (hero.contains(e.target)) return;
      if (panel && panel.contains(e.target)) return;
      hidePanel();
    });

    var api = {
      hidePanel: hidePanel,
      buscar: ejecutarBusqueda,
      focus: function () {
        input.focus();
      },
    };

    initFiltros(api);

    return api;
  }

  window.PreciosPilotoBusqueda = { init: initBusqueda };
})();
