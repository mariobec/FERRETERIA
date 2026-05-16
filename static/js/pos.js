/**
 * Punto de venta: buscador, líneas, cliente y atajos.
 * URLs inyectadas desde #pos-config (JSON).
 */
(function () {
  function readPosConfig() {
    const el = document.getElementById("pos-config");
    if (!el || !el.textContent) return null;
    try {
      return JSON.parse(el.textContent);
    } catch (e) {
      return null;
    }
  }

  /** Después de validar RUT contra el servidor, devuelve el foco al lector / escáner de productos. */
  function posFocusBarcodeWedgeSoon() {
    requestAnimationFrame(function () {
      setTimeout(function () {
        const wedge = document.getElementById("posBarcodeWedge");
        if (!wedge || wedge.disabled) return;
        wedge.focus({ preventScroll: false });
        try {
          wedge.select();
        } catch (_e) {
          /* algunos mobile */
        }
      }, 80);
    });
  }

  function formatoCLP(valor) {
    return new Intl.NumberFormat("es-CL", { style: "currency", currency: "CLP" }).format(valor);
  }

  /**
   * Asistente de búsqueda manual: input único + panel de tarjetas (sin Select2 visible).
   */
  function initPosManualSearch(buscarUrl) {
    const panel = document.getElementById("pos-search-suggestions");
    const input = document.getElementById("posBuscarManual");
    const hero = document.querySelector(".pos-manual-search-hero");
    if (!panel || !input || !buscarUrl) return null;

    function setSuggestOpen(open) {
      if (hero) hero.classList.toggle("pos-manual-search-hero--suggest-open", !!open);
    }

    let activeIndex = -1;
    let lastItems = [];
    let debounceTimer = null;
    let fetchCtrl = null;
    function posSoloVendiblesActivo() {
      const chk = document.getElementById("posSoloVendibles");
      return !!(chk && chk.checked);
    }

    function hidePanel() {
      panel.classList.add("d-none");
      panel.innerHTML = "";
      activeIndex = -1;
      lastItems = [];
      setSuggestOpen(false);
    }

    function escapeHtml(s) {
      return String(s || "")
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;");
    }

    function badgeClass(tipo) {
      const t = String(tipo || "").toLowerCase();
      if (t === "economica" || t === "premium" || t === "tienda" || t === "bodega" || t === "sin_stock") {
        return "pos-search-badge pos-search-badge--" + t;
      }
      return "pos-search-badge";
    }

    function stockLinea(it) {
      const u = escapeHtml(it.unidad || "un");
      const st = Number(it.stock_tienda || 0);
      const sb = Number(it.stock_bodega || 0);
      const tot = Number(it.stock_total != null ? it.stock_total : st + sb);
      if (st > 0 && sb > 0) {
        return (
          "Stock: <strong>" + tot + " " + u + "</strong> (Tienda: " + st + " / Bodega: " + sb + ")"
        );
      }
      if (st > 0) {
        return "Stock: <strong>" + st + " " + u + "</strong> (Tienda)";
      }
      if (sb > 0) {
        return "Stock: <strong>" + sb + " " + u + "</strong> (Bodega)";
      }
      return 'Stock: <strong class="text-danger">0</strong> ' + u;
    }

    function renderItems(items) {
      if (!items.length) {
        panel.innerHTML =
          '<div class="pos-search-suggestions__head">Asistente de precios</div>' +
          '<div class="pos-search-suggestions__empty">Sin coincidencias. Pruebe otro término o use Catálogo.</div>';
        panel.classList.remove("d-none");
        setSuggestOpen(true);
        return;
      }
      const html = items
        .map(function (it, idx) {
          const badges = (it.badges || [])
            .map(function (b) {
              return (
                '<span class="' +
                badgeClass(b.tipo) +
                '">' +
                escapeHtml(b.label || "") +
                "</span>"
              );
            })
            .join("");
          const marca = (it.marca || "").trim();
          const meta = "SKU: " + escapeHtml(it.codigo || "") + (marca ? " · Marca: " + escapeHtml(marca) : "");
          return (
            '<article class="pos-search-card' +
            (idx === activeIndex ? " is-active" : "") +
            '" role="option" data-idx="' +
            idx +
            '" data-producto-id="' +
            escapeHtml(it.producto_id) +
            '" aria-selected="' +
            (idx === activeIndex ? "true" : "false") +
            '">' +
            '<div class="pos-search-card__main">' +
            '<p class="pos-search-card__title">' +
            escapeHtml(it.nombre || it.text || "") +
            "</p>" +
            '<p class="pos-search-card__meta">' +
            meta +
            "</p>" +
            '<p class="pos-search-card__stock">' +
            stockLinea(it) +
            "</p>" +
            "</div>" +
            '<div class="pos-search-card__right">' +
            '<div class="pos-search-card__price-label">P. LISTA</div>' +
            '<div class="pos-search-card__price">' +
            escapeHtml(it.precio_fmt || formatoCLP(it.precio || 0)) +
            "</div>" +
            (badges ? '<div class="pos-search-card__badges">' + badges + "</div>" : "") +
            '<div class="pos-search-card__add"><i class="fas fa-plus"></i> Agregar</div>' +
            "</div>" +
            "</article>"
          );
        })
        .join("");
      panel.innerHTML =
        '<div class="pos-search-suggestions__head">Asistente de precios · ' +
        items.length +
        " resultado" +
        (items.length === 1 ? "" : "s") +
        "</div>" +
        html;
      panel.classList.remove("d-none");
      setSuggestOpen(true);
      panel.querySelectorAll(".pos-search-card").forEach(function (card) {
        card.addEventListener("mousedown", function (e) {
          e.preventDefault();
          const idx = parseInt(card.getAttribute("data-idx"), 10);
          if (!isNaN(idx)) seleccionarItem(idx);
        });
      });
    }

    function marcarActivo() {
      panel.querySelectorAll(".pos-search-card").forEach(function (el, i) {
        el.classList.toggle("is-active", i === activeIndex);
        el.setAttribute("aria-selected", i === activeIndex ? "true" : "false");
      });
      const active = panel.querySelector(".pos-search-card.is-active");
      if (active && typeof active.scrollIntoView === "function") {
        active.scrollIntoView({ block: "nearest" });
      }
    }

    function seleccionarItem(idx) {
      const it = lastItems[idx];
      if (!it || it.producto_id == null) return;
      hidePanel();
      input.value = "";
      posEscanearYAgregar(String(it.producto_id), true);
    }

    function ejecutarBusqueda(term) {
      const q = (term || "").trim();
      if (q.length < 3) {
        hidePanel();
        return;
      }
      if (fetchCtrl) fetchCtrl.abort();
      fetchCtrl = new AbortController();
      panel.innerHTML =
        '<div class="pos-search-suggestions__head">Asistente de precios</div>' +
        '<div class="pos-search-suggestions__loading"><i class="fas fa-spinner fa-spin me-1"></i> Buscando…</div>';
      panel.classList.remove("d-none");
      setSuggestOpen(true);

      const params = new URLSearchParams({
        q: q,
        origen: "pos",
        enriquecido: "1",
        solo_vendibles: posSoloVendiblesActivo() ? "1" : "0",
      });
      fetch(buscarUrl + "?" + params.toString(), {
        credentials: "same-origin",
        headers: { Accept: "application/json" },
        signal: fetchCtrl.signal,
      })
        .then(function (r) {
          return r.json();
        })
        .then(function (data) {
          lastItems = data && Array.isArray(data.results) ? data.results : [];
          activeIndex = lastItems.length ? 0 : -1;
          if (lastItems.length) {
            renderItems(lastItems);
          } else {
            panel.innerHTML =
              '<div class="pos-search-suggestions__head">Asistente de precios</div>' +
              '<div class="pos-search-suggestions__empty">Sin coincidencias. Pruebe otro término o use Catálogo.</div>';
            panel.classList.remove("d-none");
            setSuggestOpen(true);
          }
        })
        .catch(function (err) {
          if (err && err.name === "AbortError") return;
          panel.innerHTML =
            '<div class="pos-search-suggestions__head">Asistente de precios</div>' +
            '<div class="pos-search-suggestions__empty">No se pudo cargar la búsqueda.</div>';
          panel.classList.remove("d-none");
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
          const q = (input.value || "").trim();
          if (q.length >= 3) {
            e.preventDefault();
            ejecutarBusqueda(q);
          }
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
      } else if (e.key === "Enter" && activeIndex >= 0) {
        e.preventDefault();
        e.stopPropagation();
        seleccionarItem(activeIndex);
      }
    }


    input.addEventListener("input", function () {
      clearTimeout(debounceTimer);
      const term = (input.value || "").trim();
      if (term.length < 3) {
        hidePanel();
        return;
      }
      debounceTimer = setTimeout(function () {
        ejecutarBusqueda(term);
      }, 280);
    });

    input.addEventListener("focus", function () {
      const term = (input.value || "").trim();
      if (term.length >= 3 && !lastItems.length) {
        ejecutarBusqueda(term);
      }
    });

    input.addEventListener("keydown", onInputKeydown);

    document.addEventListener("click", function (e) {
      if (!hero) return;
      if (hero.contains(e.target)) return;
      hidePanel();
    });

    const formBusqueda = document.getElementById("formAgregarProductoBusqueda");
    if (formBusqueda) {
      formBusqueda.addEventListener("submit", function (e) {
        const hidPid = document.getElementById("posSeleccionProductoId");
        if (hidPid && hidPid.value) return;
        if (lastItems.length && activeIndex >= 0) {
          e.preventDefault();
          seleccionarItem(activeIndex);
          return;
        }
        const q = (input.value || "").trim();
        e.preventDefault();
        if (q.length >= 3) {
          ejecutarBusqueda(q);
          mostrarPosToast("Elija un producto de la lista (flechas y Enter).");
        } else {
          mostrarPosToast("Escriba al menos 3 caracteres para buscar.");
        }
      });
    }

    return { hidePanel: hidePanel, focusInput: function () { input.focus(); input.select(); } };
  }

  function actualizarTotalesVisuales(total) {
    const rounded = Math.round(total || 0);
    const totalFmt = formatoCLP(rounded);
    const main = document.getElementById("monto_total");
    const cockpit = document.getElementById("monto_total_cockpit");
    if (main) {
      main.innerText = totalFmt;
      main.setAttribute("data-pos-total-clp", String(rounded));
    }
    if (cockpit) {
      cockpit.innerText = totalFmt;
      cockpit.setAttribute("data-pos-total-clp", String(rounded));
    }
    const dockCount = document.getElementById("posDockItemCount");
    if (dockCount) {
      const n = document.querySelectorAll(".table-ds tbody tr[id^='pos_row_']").length;
      dockCount.textContent = String(n);
    }
  }

  function posLeerTotalClpDesdeMontoEl() {
    const totalEl = document.getElementById("monto_total");
    if (!totalEl) return 0;
    const d = totalEl.getAttribute("data-pos-total-clp");
    if (d != null && String(d).trim() !== "") {
      const n = parseInt(String(d).trim(), 10);
      if (!isNaN(n)) return Math.max(0, n);
    }
    const raw = (totalEl.textContent || "").replace(/[^\d]/g, "");
    return parseInt(raw, 10) || 0;
  }

  function posSumarSubtotalesFilasBrutas() {
    let s = 0;
    document.querySelectorAll("[id^='subtotal_']").forEach(function (cell) {
      const t = (cell.textContent || "").trim();
      const n = parseFloat(t.replace(/[^0-9.-]/g, ""));
      if (!isNaN(n)) s += n;
    });
    return Math.round(s);
  }

  let posUltimoCodigoEscaneado = "";
  let posModalProductoNoEncontrado = null;
  let posModalProductoAltaRapida = null;

  function openPosProductoNoEncontradoModal(codigo, sugerencias) {
    const el = document.getElementById("modalPosProductoNoEncontrado");
    if (!el || typeof bootstrap === "undefined") {
      mostrarPosToast("Producto no encontrado: " + (codigo || ""));
      return;
    }
    posUltimoCodigoEscaneado = codigo || "";
    const show = document.getElementById("posScanCodigoMostrar");
    if (show) show.textContent = codigo || "";
    const wrap = document.getElementById("posScanSugerencias");
    const lista = document.getElementById("posScanSugerenciasLista");
    if (lista && wrap) {
      lista.innerHTML = "";
      if (sugerencias && sugerencias.length) {
        wrap.classList.remove("d-none");
        sugerencias.forEach(function (s) {
          const b = document.createElement("button");
          b.type = "button";
          b.className = "btn btn-sm btn-outline-secondary";
          b.textContent = (s.nombre || "").slice(0, 40);
          b.addEventListener("click", function () {
            posEscanearYAgregar(String(s.id), true);
          });
          lista.appendChild(b);
        });
      } else {
        wrap.classList.add("d-none");
      }
    }
    if (!posModalProductoNoEncontrado) {
      posModalProductoNoEncontrado = bootstrap.Modal.getOrCreateInstance(el);
    }
    posModalProductoNoEncontrado.show();
  }

  function openPosProductoAltaRapidaModal(codigo) {
    const el = document.getElementById("modalPosProductoAltaRapida");
    if (!el) return;
    const c = document.getElementById("posAltaCodigo");
    const n = document.getElementById("posAltaNombre");
    const err = document.getElementById("posProductoAltaError");
    if (c) c.value = codigo || posUltimoCodigoEscaneado || "";
    if (n) {
      n.value = "";
      setTimeout(function () { n.focus(); }, 200);
    }
    if (err) {
      err.classList.add("d-none");
      err.textContent = "";
    }
    if (!posModalProductoAltaRapida) {
      posModalProductoAltaRapida = bootstrap.Modal.getOrCreateInstance(el);
    }
    if (posModalProductoNoEncontrado) posModalProductoNoEncontrado.hide();
    posModalProductoAltaRapida.show();
  }

  async function posEscanearYAgregar(codigo, porProductoId) {
    const cfg = readPosConfig();
    const url = cfg && cfg.urls && cfg.urls.escanear_agregar;
    if (!url) return;
    const payload = porProductoId ? { producto_id: codigo } : { codigo: codigo };
    try {
      const res = await fetch(url, {
        method: "POST",
        credentials: "same-origin",
        headers: { "Content-Type": "application/json", Accept: "application/json" },
        body: JSON.stringify(payload),
      });
      const data = await res.json().catch(function () { return {}; });
      if (res.ok && data.ok) {
        const nom = data.producto_nombre || "producto";
        const msg = data.linea_incrementada
          ? "Cantidad " + (data.cantidad_en_vale || "") + ": " + nom
          : "Agregado: " + nom;
        mostrarPosToast(msg);
        window.location.reload();
        return;
      }
      if (data.error === "no_encontrado") {
        openPosProductoNoEncontradoModal(data.codigo || codigo, data.sugerencias || []);
        return;
      }
      if (data.error === "sin_stock" || data.error === "en_vale_pendiente") {
        mostrarPosToast(data.mensaje || "Sin stock suficiente en tienda.");
        return;
      }
      mostrarPosToast(data.mensaje || data.error || "No se pudo agregar el producto.");
    } catch (e) {
      mostrarPosToast("Error de red al escanear.");
    }
  }

  async function guardarPosProductoAltaRapida() {
    const cfg = readPosConfig();
    const url = cfg && cfg.urls && cfg.urls.producto_alta_rapida;
    if (!url) return;
    const nombre = (document.getElementById("posAltaNombre") || {}).value || "";
    const codigo = (document.getElementById("posAltaCodigo") || {}).value || "";
    const precio = parseFloat((document.getElementById("posAltaPrecio") || {}).value || "0");
    const stock = parseInt((document.getElementById("posAltaStock") || {}).value || "1", 10);
    const err = document.getElementById("posProductoAltaError");
    if (!(nombre || "").trim()) {
      if (err) {
        err.textContent = "Ingrese el nombre del producto.";
        err.classList.remove("d-none");
      }
      return;
    }
    if (!precio || precio <= 0) {
      if (err) {
        err.textContent = "Ingrese un precio de venta válido.";
        err.classList.remove("d-none");
      }
      return;
    }
    const btn = document.getElementById("posBtnGuardarAltaProducto");
    if (btn) btn.disabled = true;
    try {
      const res = await fetch(url, {
        method: "POST",
        credentials: "same-origin",
        headers: { "Content-Type": "application/json", Accept: "application/json" },
        body: JSON.stringify({
          codigo_barra: codigo,
          nombre: nombre.trim(),
          precio_venta: precio,
          stock_tienda: stock,
          agregar_vale: true,
        }),
      });
      const data = await res.json().catch(function () { return {}; });
      if (res.ok && data.ok) {
        if (posModalProductoAltaRapida) posModalProductoAltaRapida.hide();
        mostrarPosToast("Producto creado: " + (data.producto_nombre || nombre));
        window.location.reload();
        return;
      }
      if (err) {
        err.textContent = data.mensaje || data.error || "No se pudo crear el producto.";
        err.classList.remove("d-none");
      }
    } catch (e) {
      if (err) {
        err.textContent = "Error de red.";
        err.classList.remove("d-none");
      }
    }
    if (btn) btn.disabled = false;
  }

  function actualizarSubtotal(detalleId, precioUnitario) {
    const cantidad = parseFloat(document.getElementById("cantidad_" + detalleId).value) || 0;
    const descuento = parseFloat(document.getElementById("descuento_" + detalleId).value) || 0;
    const factorStock = parseFloat(document.getElementById("cantidad_" + detalleId).dataset.factorStock || "1") || 1;
    const subtotal = cantidad * precioUnitario * (1 - descuento / 100);
    document.getElementById("subtotal_" + detalleId).innerText = formatoCLP(subtotal);
    const consumoEl = document.getElementById("consumo_stock_" + detalleId);
    if (consumoEl) {
      consumoEl.innerText = Math.max(0, Math.round(cantidad * factorStock));
    }

    let total = 0;
    document.querySelectorAll("[id^='subtotal_']").forEach(function (cell) {
      const valor = cell.innerText.replace(/[^0-9]/g, "");
      total += parseFloat(valor) || 0;
    });
    actualizarTotalesVisuales(total);
    document.getElementById("precio_unitario_" + detalleId).innerText = formatoCLP(precioUnitario);
  }

  function validarStockLinea(detalleId) {
    const cantidadEl = document.getElementById("cantidad_" + detalleId);
    if (!cantidadEl) return false;
    const cantidad = parseFloat(cantidadEl.value) || 0;
    const factorStock = parseFloat(cantidadEl.dataset.factorStock || "1") || 1;
    const stockDisponible = parseFloat(cantidadEl.dataset.stockDisponible || "0") || 0;
    const consumo = Math.max(0, Math.round(cantidad * factorStock));
    const excede = consumo > stockDisponible;

    const row = document.getElementById("pos_row_" + detalleId);
    const alertEl = document.getElementById("stock_alert_" + detalleId);
    if (row) row.classList.toggle("pos-row-stock-error", excede);
    if (alertEl) alertEl.classList.toggle("d-none", !excede);
    return excede;
  }

  function actualizarEstadoValidacionStock() {
    let hayExceso = false;
    document.querySelectorAll(".cantidad-input").forEach(function (input) {
      const detalleId = input.dataset.detalleId;
      if (!detalleId) return;
      if (validarStockLinea(detalleId)) hayExceso = true;
    });
    const alertaGlobal = document.getElementById("stockValidationAlert");
    if (alertaGlobal) alertaGlobal.classList.toggle("d-none", !hayExceso);
    return hayExceso;
  }

  function puntoRetiroValido() {
    const cfg = readPosConfig();
    if (cfg && cfg.pos_retiro_por_linea) {
      return true;
    }
    const select = document.getElementById("punto_retiro");
    if (!select) return false;
    const valor = (select.value || "").trim();
    return valor !== "" && valor !== "__PENDIENTE__";
  }

  function posContarItemsVale() {
    const filas = document.querySelectorAll("[id^='pos_row_']");
    if (filas.length) return filas.length;
    const dock = document.getElementById("posDockItemCount");
    if (dock) return parseInt(dock.textContent || "0", 10) || 0;
    return document.querySelectorAll(".cantidad-input").length;
  }

  function posTotalValeEsCero() {
    const totalEl = document.getElementById("monto_total");
    if (!totalEl) return true;
    const raw = (totalEl.textContent || totalEl.innerText || "").replace(/[^\d]/g, "");
    return (parseInt(raw, 10) || 0) <= 0;
  }

  function posValeEstaVacio() {
    return posContarItemsVale() === 0 || posTotalValeEsCero();
  }

  function actualizarEstadoEmisionVale() {
    const hayExcesoStock = actualizarEstadoValidacionStock();
    const vacia = posValeEstaVacio();
    const btnEmitir = document.getElementById("emitirValeBtn");
    if (btnEmitir) {
      btnEmitir.disabled = hayExcesoStock || vacia;
      btnEmitir.title = vacia
        ? "Escanee o busque productos antes de emitir"
        : hayExcesoStock
          ? "Corrija stock insuficiente antes de emitir"
          : "";
    }
  }

  function ajustarCantidad(detalleId, delta, precioUnitario) {
    const input = document.getElementById("cantidad_" + detalleId);
    let actual = parseInt(input.value || "1", 10);
    actual = Math.max(1, actual + delta);
    input.value = actual;
    actualizarSubtotal(detalleId, precioUnitario);
  }

  function mostrarPosToast(mensaje) {
    const body = document.getElementById("posToastBody");
    if (!body) return;
    body.innerText = mensaje;
    const toastEl = document.getElementById("posToast");
    if (!toastEl || typeof bootstrap === "undefined") return;
    const toast = bootstrap.Toast.getOrCreateInstance(toastEl, { delay: 1500 });
    toast.show();
  }

  function escapeHtmlPosJs(str) {
    if (str == null || str === "") return "";
    const d = document.createElement("div");
    d.textContent = str;
    return d.innerHTML;
  }

  const DEBOUNCE_PERSIST_MS = 650;
  const EPS_DESC = 1e-6;
  const persistTimers = {};
  let pendingDetalleIdAutorizacionDesc = null;

  function cancelPersistDetalle(detalleId) {
    if (persistTimers[detalleId]) {
      clearTimeout(persistTimers[detalleId]);
      delete persistTimers[detalleId];
    }
  }

  function schedulePersistDetalle(detalleId, urlActualizarItem, soloCantidad) {
    cancelPersistDetalle(detalleId);
    persistTimers[detalleId] = setTimeout(function () {
      delete persistTimers[detalleId];
      actualizarItem(detalleId, urlActualizarItem, { solo_cantidad: !!soloCantidad });
    }, DEBOUNCE_PERSIST_MS);
  }

  function isTypingInField(target) {
    if (!target || !target.tagName) return false;
    const t = target.tagName.toUpperCase();
    if (t === "TEXTAREA" || t === "SELECT") return true;
    if (t === "INPUT") {
      const type = (target.type || "").toLowerCase();
      if (["button", "submit", "checkbox", "radio", "range", "file", "hidden"].indexOf(type) !== -1) {
        return false;
      }
      return true;
    }
    return false;
  }

  function actualizarItem(detalleId, urlActualizarItem, opts) {
    opts = opts || {};
    const cantidad = document.getElementById("cantidad_" + detalleId).value;
    const descuento = document.getElementById("descuento_" + detalleId).value;
    const form = document.createElement("form");
    form.method = "POST";
    form.action = urlActualizarItem;

    const fActualizar = document.createElement("input");
    fActualizar.type = "hidden";
    fActualizar.name = "actualizar";
    fActualizar.value = detalleId;
    form.appendChild(fActualizar);

    if (opts.solo_cantidad) {
      const fs = document.createElement("input");
      fs.type = "hidden";
      fs.name = "solo_cantidad";
      fs.value = "1";
      form.appendChild(fs);
    }

    const fCantidad = document.createElement("input");
    fCantidad.type = "hidden";
    fCantidad.name = "cantidad_" + detalleId;
    fCantidad.value = cantidad;
    form.appendChild(fCantidad);

    const fDescuento = document.createElement("input");
    fDescuento.type = "hidden";
    fDescuento.name = "descuento_" + detalleId;
    fDescuento.value = descuento;
    form.appendChild(fDescuento);

    if (opts.supervisor_identificador) {
      const fc = document.createElement("input");
      fc.type = "hidden";
      fc.name = "supervisor_identificador";
      fc.value = opts.supervisor_identificador;
      form.appendChild(fc);
    }
    if (opts.supervisor_clave) {
      const fp = document.createElement("input");
      fp.type = "hidden";
      fp.name = "supervisor_clave";
      fp.value = opts.supervisor_clave;
      form.appendChild(fp);
    }

    const cfgDeck = readPosConfig();
    if (cfgDeck && cfgDeck.from_command_deck) {
      const fd = document.createElement("input");
      fd.type = "hidden";
      fd.name = "from_command_deck";
      fd.value = "1";
      form.appendChild(fd);
    }

    document.body.appendChild(form);
    mostrarPosToast(opts.solo_cantidad ? "Guardando cantidad..." : "Guardando cambios del item...");
    form.submit();
  }

  function descuentoRequiereCredencialSupervisor(detalleId, descLibre) {
    if (descLibre) return false;
    const descEl = document.getElementById("descuento_" + detalleId);
    if (!descEl) return false;
    const descServidor = parseFloat(descEl.dataset.descuentoServidor || "0") || 0;
    const descNuevo = parseFloat(descEl.value || "0") || 0;
    return descNuevo > descServidor + EPS_DESC;
  }

  let posClienteUiEstado = "idle";

  function posRutQuickInput() {
    return document.getElementById("posIdentRutQuick") || document.getElementById("deckClienteRutQuick");
  }

  function getClienteRutForSearch() {
    const q = posRutQuickInput();
    const hidden = document.getElementById("cliente_rut");
    if (q && (q.value || "").trim()) return (q.value || "").trim();
    return hidden ? (hidden.value || "").trim() : "";
  }

  function setClienteRutEverywhere(rut) {
    const q = posRutQuickInput();
    const hidden = document.getElementById("cliente_rut");
    if (q) q.value = rut || "";
    if (hidden) hidden.value = rut || "";
  }

  function setHiddenClienteField(id, val) {
    const el = document.getElementById(id);
    if (el) el.value = val == null ? "" : String(val);
  }

  function posNotifyExperienceWallRefresh() {
    try {
      window.dispatchEvent(new CustomEvent("pos-experience-wall-refresh"));
    } catch (e) {}
  }

  let posClienteNuevoModalInst = null;

  function posClienteModalError(msg) {
    const el = document.getElementById("posClienteModalError");
    if (!el) return;
    if (!msg) {
      el.classList.add("d-none");
      el.textContent = "";
      return;
    }
    el.textContent = msg;
    el.classList.remove("d-none");
  }

  function openPosClienteNuevoModal(resumen) {
    const modalEl = document.getElementById("modalPosClienteNuevo");
    if (!modalEl || typeof bootstrap === "undefined") return false;
    const rutVal = (resumen && resumen.rut) || getClienteRutForSearch();
    const rutIn = document.getElementById("posClienteModalRut");
    const nomIn = document.getElementById("posClienteModalNombre");
    const telIn = document.getElementById("posClienteModalTelefono");
    if (rutIn) rutIn.value = rutVal || "";
    if (nomIn) nomIn.value = (resumen && resumen.nombre) || "";
    if (telIn) telIn.value = (resumen && resumen.telefono) || "";
    posClienteModalError("");
    setHiddenClienteField("cliente_rut", rutVal);
    if (!posClienteNuevoModalInst) {
      posClienteNuevoModalInst = bootstrap.Modal.getOrCreateInstance(modalEl);
    }
    posClienteNuevoModalInst.show();
    if (nomIn) setTimeout(function () { nomIn.focus(); }, 200);
    return true;
  }

  async function guardarPosClienteNuevoModal() {
    const nomIn = document.getElementById("posClienteModalNombre");
    const telIn = document.getElementById("posClienteModalTelefono");
    const rutIn = document.getElementById("posClienteModalRut");
    const nombre = nomIn ? nomIn.value.trim() : "";
    const telefono = telIn ? telIn.value.trim() : "";
    const rut = rutIn ? rutIn.value.trim() : getClienteRutForSearch();
    if (!nombre) {
      posClienteModalError("Ingrese el nombre o razón social.");
      if (nomIn) nomIn.focus();
      return false;
    }
    posClienteModalError("");
    const btn = document.getElementById("posBtnGuardarClienteNuevo");
    if (btn) btn.disabled = true;
    const res = await vincularClienteEnVale({
      cliente_rut: rut,
      registrar: true,
      nombre: nombre,
      telefono: telefono,
    });
    if (btn) btn.disabled = false;
    if (!res || !res.ok) {
      const err = (res && res.error) || "no_pudo_registrar";
      const msgs = {
        nombre_requerido: "El nombre es obligatorio.",
        rut_invalido: "RUT inválido.",
        cliente_no_existe: "No se pudo registrar el cliente.",
        no_pudo_registrar: "Error al guardar en la base de datos.",
        sin_venta_abierta: "No hay vale abierto.",
        sin_caja: "Debe abrir caja.",
        sin_permiso: "Sin permiso para esta acción.",
      };
      posClienteModalError(msgs[err] || "No se pudo guardar el cliente.");
      return false;
    }
    const cli = res.cliente || {};
    setClienteRutEverywhere(rut);
    setHiddenClienteField("cliente_nombre", cli.nombre || nombre);
    setHiddenClienteField("cliente_telefono", cli.telefono || telefono);
    setPosClienteUiState("known", {
      nombre: cli.nombre || nombre,
      rut: rut,
      saldo_favor: Number(cli.saldo_favor || 0),
    });
    if (posClienteNuevoModalInst) posClienteNuevoModalInst.hide();
    renderPosTvClienteBadge(res.cliente_vitrina);
    posNotifyExperienceWallRefresh();
    mostrarPosToast("Cliente registrado y vinculado al vale.");
    return true;
  }

  function setPosClienteUiState(estado, resumen) {
    posClienteUiEstado = estado || "idle";
    const map = {
      idle: "posClientePanelIdle",
      known: "posClientePanelKnown",
      final: "posClientePanelFinal",
    };
    const panelEstado = posClienteUiEstado === "new" ? "idle" : posClienteUiEstado;
    Object.keys(map).forEach(function (k) {
      const el = document.getElementById(map[k]);
      if (el) el.classList.toggle("d-none", k !== panelEstado);
    });
    const chk = document.getElementById("cliente_final");
    if (chk) chk.checked = posClienteUiEstado === "final";

    if (posClienteUiEstado === "known" && resumen) {
      const nom = document.getElementById("posClienteKnownNombre");
      const rutEl = document.getElementById("posClienteKnownRut");
      if (nom) nom.textContent = resumen.nombre || "—";
      if (rutEl) rutEl.textContent = resumen.rut || "";
      const extras = document.getElementById("posClienteKnownExtras");
      if (extras) {
        let html = "";
        if (Number(resumen.saldo_favor || 0) > 0) {
          html +=
            '<div class="alert alert-warning py-2 px-3 mb-0 small"><i class="fas fa-wallet me-1"></i>Saldo a favor: <strong>' +
            formatoCLP(Number(resumen.saldo_favor)) +
            "</strong></div>";
        }
        extras.innerHTML = html;
      }
      setHiddenClienteField("cliente_rut", resumen.rut);
      setHiddenClienteField("cliente_nombre", resumen.nombre);
    } else if (posClienteUiEstado === "new") {
      const rutVal = (resumen && resumen.rut) || getClienteRutForSearch();
      setHiddenClienteField("cliente_rut", rutVal);
      openPosClienteNuevoModal(resumen || { rut: rutVal });
    } else if (posClienteUiEstado === "final") {
      setHiddenClienteField("cliente_rut", "");
      setHiddenClienteField("cliente_nombre", "");
    }
  }

  function syncHiddenClienteFromPanels() {
    if (posClienteUiEstado === "final") return;
    if (posClienteUiEstado === "new") {
      const nn = document.getElementById("posClienteModalNombre");
      const nt = document.getElementById("posClienteModalTelefono");
      const nr = document.getElementById("posClienteModalRut");
      setHiddenClienteField("cliente_nombre", nn ? nn.value.trim() : "");
      setHiddenClienteField("cliente_telefono", nt ? nt.value.trim() : "");
      if (nr) setHiddenClienteField("cliente_rut", nr.value.trim());
    }
  }

  function initPosClienteUiFromConfig(cfg) {
    const ui = cfg && cfg.cliente_ui;
    if (ui) {
      if (ui.estado === "known" && ui.resumen) {
        setPosClienteUiState("known", ui.resumen);
        return;
      }
      if (ui.estado === "final") {
        setPosClienteUiState("final");
        return;
      }
      if (ui.estado === "new") {
        setPosClienteUiState("new", ui.resumen || { rut: getClienteRutForSearch() });
        return;
      }
    }
    const rut = getClienteRutForSearch();
    const nombre = document.getElementById("cliente_nombre");
    if (rut) {
      setPosClienteUiState("known", {
        rut: rut,
        nombre: nombre ? nombre.value : "",
        saldo_favor: (ui && ui.resumen && ui.resumen.saldo_favor) || 0,
      });
    } else {
      setPosClienteUiState("idle");
    }
  }

  let posRutObligatorioEnabled = true;

  function posRutObligatorio() {
    return posRutObligatorioEnabled;
  }

  function posSyncExigirRutHidden() {
    const hid = document.getElementById("posExigirRutVenta");
    if (hid) hid.value = posRutObligatorioEnabled ? "1" : "0";
  }

  function aplicarClienteFinalSiRutOpcional() {
    if (posRutObligatorio()) return;
    const chk = document.getElementById("cliente_final");
    const rut = (getClienteRutForSearch() || "").replace(/\./g, "").replace(/-/g, "").trim();
    if (chk && posClienteUiEstado === "idle" && !rut) {
      chk.checked = true;
      syncClienteFinalMode(false);
    }
  }

  function validarRutCliente() {
    const chk = document.getElementById("cliente_final");
    const rutErr = document.getElementById("rut_error");
    if (chk && chk.checked) {
      if (rutErr) rutErr.classList.add("d-none");
      return true;
    }
    if (posClienteUiEstado === "idle") {
      if (!posRutObligatorio()) {
        aplicarClienteFinalSiRutOpcional();
        if (rutErr) rutErr.classList.add("d-none");
        return true;
      }
      if (rutErr) {
        rutErr.textContent = "Identifique cliente (RUT) o pulse F3 para cliente final.";
        rutErr.classList.remove("d-none");
      }
      mostrarPosToast("Identifique cliente (RUT) o use cliente final (F3).");
      return false;
    }
    if (posClienteUiEstado === "new") {
      syncHiddenClienteFromPanels();
      const nombre = document.getElementById("cliente_nombre");
      if (!nombre || !(nombre.value || "").trim()) {
        openPosClienteNuevoModal({ rut: getClienteRutForSearch() });
        mostrarPosToast("Complete y guarde los datos del cliente nuevo.");
        return false;
      }
    }
    const rutSrc = document.getElementById("cliente_rut");
    const rut = (rutSrc ? rutSrc.value : getClienteRutForSearch())
      .replace(/\./g, "")
      .replace(/-/g, "")
      .toUpperCase();
    if (!rut || rut.length < 8) {
      if (rutErr) rutErr.classList.remove("d-none");
      return false;
    }
    const cuerpo = rut.slice(0, -1);
    const dvIngresado = rut.slice(-1);
    let suma = 0;
    const factores = [2, 3, 4, 5, 6, 7];
    let i = 0;
    for (let j = cuerpo.length - 1; j >= 0; j--) {
      suma += parseInt(cuerpo[j], 10) * factores[i];
      i = (i + 1) % 6;
    }
    const resto = 11 - (suma % 11);
    const dvEsperado = resto === 11 ? "0" : resto === 10 ? "K" : resto.toString();
    if (dvIngresado !== dvEsperado) {
      if (rutErr) rutErr.classList.remove("d-none");
      return false;
    }
    if (rutErr) rutErr.classList.add("d-none");
    return true;
  }

  function syncClienteFinalMode(fromUserChange) {
    const chk = document.getElementById("cliente_final");
    if (!chk) return;
    if (chk.checked) {
      setPosClienteUiState("final");
    } else if (posClienteUiEstado === "final") {
      setPosClienteUiState("idle");
    }
    if (fromUserChange) {
      if (chk.checked) {
        vincularClienteEnVale({ cliente_final: true }).then(function (v) {
          if (v && v.ok) {
            renderPosTvClienteBadge(v.cliente_vitrina);
            posNotifyExperienceWallRefresh();
          }
        });
      } else {
        vincularClienteEnVale({ limpiar: true }).then(function () {
          renderPosTvClienteBadge(null);
          posNotifyExperienceWallRefresh();
        });
      }
    }
  }

  function posClienteCampoStr(v) {
    if (v == null || v === "") return "";
    const s = String(v).trim();
    if (!s || /^(none|null|undefined|nan)$/i.test(s)) return "";
    return s;
  }

  async function vincularClienteEnVale(payload) {
    const cfg = readPosConfig();
    const url = cfg && cfg.urls && cfg.urls.vincular_cliente;
    if (!url) return null;
    try {
      const res = await fetch(url, {
        method: "POST",
        credentials: "same-origin",
        headers: { "Content-Type": "application/json", Accept: "application/json" },
        body: JSON.stringify(payload || {}),
      });
      return await res.json();
    } catch (e) {
      return null;
    }
  }

  function renderPosTvClienteBadge(cv) {
    const el = document.getElementById("posTvClienteBadge");
    if (!el) return;
    if (!cv) {
      el.innerHTML = "";
      return;
    }
    if (cv.es_cliente_final) {
      el.innerHTML =
        '<span class="badge rounded-pill text-bg-secondary"><i class="fas fa-tv me-1"></i>Pantalla: venta mostrador</span>';
      return;
    }
    let parts = [];
    if (cv.nombre_publico) {
      parts.push(
        '<span class="badge rounded-pill text-bg-info"><i class="fas fa-tv me-1"></i>TV: Hola, ' +
          escapeHtmlPosJs(cv.nombre_publico) +
          "</span>"
      );
    }
    if (cv.saldo_favor > 0) {
      parts.push(
        '<span class="badge rounded-pill text-bg-warning text-dark"><i class="fas fa-wallet me-1"></i>Saldo a favor visible en TV</span>'
      );
    }
    if (cv.credito_activo) {
      parts.push(
        '<span class="badge rounded-pill text-bg-success"><i class="fas fa-credit-card me-1"></i>Cliente con crédito</span>'
      );
    }
    if (cv.credito_bloqueado) {
      parts.push(
        '<span class="badge rounded-pill text-bg-danger"><i class="fas fa-ban me-1"></i>Crédito bloqueado</span>'
      );
    }
    el.innerHTML = parts.join(" ");
  }

  async function buscarClientePorRut(urlConsultarCliente) {
    const status = document.getElementById("clienteStatus");
    const nombre = document.getElementById("cliente_nombre");
    const direccion = document.getElementById("cliente_direccion");
    const giro = document.getElementById("cliente_giro");
    const comuna = document.getElementById("cliente_comuna");
    const ciudad = document.getElementById("cliente_ciudad");
    const telefono = document.getElementById("cliente_telefono");
    const correo = document.getElementById("cliente_correo");
    const rut = getClienteRutForSearch();
    if (!rut) return;
    setClienteRutEverywhere(rut);
    const rutNorm = rut.replace(/\./g, "").replace(/-/g, "").toUpperCase();
    if (rutNorm.length < 8) {
      const rutErr = document.getElementById("rut_error");
      if (rutErr) rutErr.classList.remove("d-none");
      return;
    }
    const rutErr = document.getElementById("rut_error");
    if (rutErr) rutErr.classList.add("d-none");
    try {
      const res = await fetch(urlConsultarCliente + "?rut=" + encodeURIComponent(rut), {
        credentials: "same-origin",
        headers: { Accept: "application/json" },
      });
      const ct = (res.headers.get("content-type") || "").toLowerCase();
      const rawText = await res.text();
      let data = null;
      if (ct.indexOf("application/json") !== -1) {
        try {
          data = JSON.parse(rawText);
        } catch (e) {
          data = null;
        }
      }
      if (!res.ok) {
        let detalle = "Código HTTP " + res.status + ".";
        if (data && data.mensaje) detalle = escapeHtmlPosJs(String(data.mensaje).slice(0, 400));
        else if (res.status === 401 || res.status === 302) detalle = "Sesión expirada; vuelva a iniciar sesión.";
        if (status) {
          status.innerHTML =
            '<span class="text-danger"><i class="fas fa-exclamation-triangle me-1"></i>No se pudo consultar cliente. ' +
            detalle +
            "</span>";
        }
        return;
      }
      if (!data) {
        if (status) {
          status.innerHTML =
            '<span class="text-danger"><i class="fas fa-exclamation-triangle me-1"></i>Respuesta inválida del servidor.</span>';
        }
        return;
      }
      if (data.existe) {
        if (nombre) nombre.value = posClienteCampoStr(data.cliente.nombre);
        if (direccion) direccion.value = posClienteCampoStr(data.cliente.direccion);
        if (giro) giro.value = posClienteCampoStr(data.cliente.giro);
        if (comuna) comuna.value = posClienteCampoStr(data.cliente.comuna);
        if (ciudad) ciudad.value = posClienteCampoStr(data.cliente.ciudad);
        if (telefono) telefono.value = posClienteCampoStr(data.cliente.telefono);
        if (correo) correo.value = posClienteCampoStr(data.cliente.correo);
        const saldoFavor = Number(data.cliente.saldo_favor || 0);
        setPosClienteUiState("known", {
          nombre: posClienteCampoStr(data.cliente.nombre),
          rut: rut,
          saldo_favor: saldoFavor,
        });
        const vinc = await vincularClienteEnVale({ cliente_rut: rut });
        if (vinc && vinc.ok) {
          renderPosTvClienteBadge(vinc.cliente_vitrina);
          posNotifyExperienceWallRefresh();
        }
        posFocusBarcodeWedgeSoon();
      } else {
        if (nombre) nombre.value = "";
        if (direccion) direccion.value = "";
        if (giro) giro.value = "";
        if (comuna) comuna.value = "";
        if (ciudad) ciudad.value = "";
        if (telefono) telefono.value = "";
        if (correo) correo.value = "";
        setPosClienteUiState("new", { rut: rut });
      }
    } catch (err) {
      if (status) {
        status.innerHTML =
          '<span class="text-danger"><i class="fas fa-exclamation-triangle me-1"></i>No se pudo consultar cliente (red o respuesta inválida).</span>';
      }
    }
  }

  document.addEventListener("DOMContentLoaded", function () {
    const cfg = readPosConfig();
    if (!cfg || !cfg.urls) return;
    const u = cfg.urls;
    const descLibre = !!cfg.descuento_libre;
    let crossSellEnabled = cfg.cross_sell_enabled !== false;
    const crossSellProductoIds = Array.isArray(cfg.producto_ids) ? cfg.producto_ids : [];
    let posAutorizadoresCache = [];

    const crossSellPanel = document.getElementById("posCrossSellPanel");
    const crossSellStateText = document.getElementById("posCrossSellStateText");
    const crossSellStateBadge = document.getElementById("posCrossSellStateBadge");
    const crossSellContent = document.getElementById("posCrossSellContent");
    const crossSellToggleBtn = document.getElementById("posToggleCrossSellBtn");
    const crossSellToggleText = document.getElementById("posToggleCrossSellText");
    const rutToggleBtn = document.getElementById("posToggleRutObligatorioBtn");
    const rutToggleText = document.getElementById("posToggleRutObligatorioText");
    const rutHintText = document.getElementById("posRutHintText");
    posRutObligatorioEnabled = cfg.pos_rut_obligatorio !== false;

    function escapeHtmlPos(str) {
      if (str == null || str === "") return "";
      const d = document.createElement("div");
      d.textContent = str;
      return d.innerHTML;
    }

    function posSetCrossSellUi(enabled) {
      crossSellEnabled = !!enabled;
      if (crossSellToggleBtn) {
        crossSellToggleBtn.dataset.enabled = crossSellEnabled ? "1" : "0";
        crossSellToggleBtn.classList.toggle("is-on", crossSellEnabled);
        crossSellToggleBtn.classList.toggle("is-off", !crossSellEnabled);
      }
      if (crossSellToggleText) {
        crossSellToggleText.textContent = crossSellEnabled ? "Sugerencias ON" : "Sugerencias OFF";
      }
      if (crossSellStateText) {
        crossSellStateText.textContent = crossSellEnabled
          ? "Activas para esta sesión de caja"
          : "Desactivadas para esta sesión de caja";
      }
      if (crossSellStateBadge) {
        crossSellStateBadge.textContent = crossSellEnabled ? "ON" : "OFF";
        crossSellStateBadge.classList.toggle("text-bg-success", crossSellEnabled);
        crossSellStateBadge.classList.toggle("text-bg-secondary", !crossSellEnabled);
      }
      if (crossSellPanel) {
        crossSellPanel.dataset.enabled = crossSellEnabled ? "1" : "0";
      }
    }

    function posRenderCrossSellPanel(sugerencia) {
      if (!crossSellContent) return;
      if (!crossSellEnabled) {
        crossSellContent.innerHTML =
          '<p class="small mb-0">Las sugerencias están apagadas. Puedes reactivarlas con el botón superior.</p>';
        return;
      }
      if (!sugerencia || !Array.isArray(sugerencia.items) || sugerencia.items.length === 0) {
        crossSellContent.innerHTML =
          '<p class="small mb-0">Aún no hay sugerencias para los productos del vale actual.</p>';
        return;
      }
      const mensaje = escapeHtmlPos(sugerencia.mensaje || "Complementos sugeridos para aumentar ticket y ayudar al cajero.");
      const botones = sugerencia.items
        .map(function (it) {
          const nombre = escapeHtmlPos(it.nombre || "Producto");
          const href = u.agregar_producto + "?producto_id=" + encodeURIComponent(String(it.id || ""));
          return '<a class="btn btn-sm btn-outline-light" href="' + href + '"><i class="fas fa-plus me-1"></i>' + nombre + "</a>";
        })
        .join("");
      crossSellContent.innerHTML =
        '<p class="small mb-2">' + mensaje + '</p><div class="pos-cross-sell-actions">' + botones + "</div>";
    }

    async function posRefreshCrossSellPanel() {
      if (!crossSellContent) return;
      if (!crossSellEnabled) {
        posRenderCrossSellPanel(null);
        return;
      }
      if (!u.cross_sell || !crossSellProductoIds.length) {
        posRenderCrossSellPanel(null);
        return;
      }
      try {
        const res = await fetch(
          u.cross_sell + "?producto_ids=" + encodeURIComponent(crossSellProductoIds.join(",")),
          {
            credentials: "same-origin",
            headers: { Accept: "application/json" },
          }
        );
        if (!res.ok) {
          crossSellContent.innerHTML =
            '<p class="small mb-0">Sugerencias: error de red o permisos (HTTP ' + res.status + ").</p>";
          return;
        }
        const data = await res.json();
        posSetCrossSellUi(data.enabled !== false);
        posRenderCrossSellPanel(data.sugerencia || null);
      } catch (_err) {
        crossSellContent.innerHTML =
          '<p class="small mb-0">No se pudieron cargar sugerencias en este momento.</p>';
      }
    }

    async function posToggleCrossSell() {
      if (!u.cross_sell_toggle || !crossSellToggleBtn) return;
      const nextEnabled = !crossSellEnabled;
      crossSellToggleBtn.disabled = true;
      try {
        const res = await fetch(u.cross_sell_toggle, {
          method: "POST",
          credentials: "same-origin",
          headers: {
            Accept: "application/json",
            "Content-Type": "application/json",
          },
          body: JSON.stringify({ enabled: nextEnabled }),
        });
        if (!res.ok) {
          mostrarPosToast("No se pudo cambiar sugerencias (verifique sesión o permiso POS).");
          return;
        }
        const data = await res.json().catch(function () {
          return {};
        });
        if (data && data.ok === false) {
          mostrarPosToast("Acción no permitida para su usuario.");
          return;
        }
        posSetCrossSellUi(data.enabled !== false);
        mostrarPosToast(data.enabled ? "Sugerencias activadas." : "Sugerencias desactivadas.");
        await posRefreshCrossSellPanel();
      } catch (_err) {
        mostrarPosToast("No se pudo cambiar el estado de sugerencias.");
      } finally {
        crossSellToggleBtn.disabled = false;
      }
    }

    function posFiltrarMostrarSugerenciasSupervisor() {
      const input = document.getElementById("posSupervisorIdentificador");
      const wrap = document.getElementById("posSupervisorSuggestWrap");
      if (!input || !wrap) return;
      const q = (input.value || "").trim().toLowerCase();
      const list = posAutorizadoresCache || [];
      let match = [];
      if (!q) {
        match = list.slice(0, 12);
      } else {
        match = list
          .filter(function (row) {
            const nom = (row.nombre || "").toLowerCase();
            const cor = (row.correo || "").toLowerCase();
            return nom.indexOf(q) !== -1 || cor.indexOf(q) !== -1;
          })
          .slice(0, 12);
      }
      wrap.innerHTML = "";
      if (match.length === 0) {
        wrap.classList.add("d-none");
        return;
      }
      match.forEach(function (row) {
        const btn = document.createElement("button");
        btn.type = "button";
        btn.className = "list-group-item list-group-item-action py-2 px-3 text-start border-0 border-bottom";
        btn.innerHTML =
          '<div class="fw-semibold">' +
          escapeHtmlPos(row.nombre) +
          '</div><div class="small text-muted text-truncate">' +
          escapeHtmlPos(row.correo) +
          "</div>";
        btn.addEventListener("click", function () {
          input.value = row.correo || "";
          wrap.classList.add("d-none");
          wrap.innerHTML = "";
          const pwdEl = document.getElementById("posSupervisorClave");
          if (pwdEl) pwdEl.focus();
        });
        wrap.appendChild(btn);
      });
      wrap.classList.remove("d-none");
    }

    function posSupervisorSuggestOutside(e) {
      const wrap = document.getElementById("posSupervisorSuggestWrap");
      const input = document.getElementById("posSupervisorIdentificador");
      if (!wrap || !input || wrap.classList.contains("d-none")) return;
      const t = e.target;
      if (wrap.contains(t) || input.contains(t)) return;
      wrap.classList.add("d-none");
    }

    document.addEventListener("mousedown", posSupervisorSuggestOutside);

    const modalAutorizaEl = document.getElementById("modalAutorizarDescuentoPos");
    if (modalAutorizaEl && typeof bootstrap !== "undefined") {
      modalAutorizaEl.addEventListener("shown.bs.modal", function () {
        const inputSup = document.getElementById("posSupervisorIdentificador");
        const urlUsu = u.usuarios_autorizar_descuento;
        function postFetch() {
          posFiltrarMostrarSugerenciasSupervisor();
          if (inputSup) inputSup.focus();
        }
        if (!urlUsu) {
          posAutorizadoresCache = [];
          postFetch();
          return;
        }
        fetch(urlUsu)
          .then(function (r) {
            return r.json();
          })
          .then(function (data) {
            posAutorizadoresCache = data.usuarios || [];
          })
          .catch(function () {
            posAutorizadoresCache = [];
          })
          .finally(postFetch);
      });
      modalAutorizaEl.addEventListener("hidden.bs.modal", function () {
        pendingDetalleIdAutorizacionDesc = null;
        const idEl = document.getElementById("posSupervisorIdentificador");
        const p = document.getElementById("posSupervisorClave");
        const wrap = document.getElementById("posSupervisorSuggestWrap");
        if (idEl) idEl.value = "";
        if (p) p.value = "";
        if (wrap) {
          wrap.classList.add("d-none");
          wrap.innerHTML = "";
        }
      });
      const btnConf = document.getElementById("posConfirmarAutorizacionDescuento");
      if (btnConf) {
        btnConf.addEventListener("click", function () {
          const ident = (document.getElementById("posSupervisorIdentificador") || {}).value;
          const pwd = (document.getElementById("posSupervisorClave") || {}).value;
          const identTrim = (ident || "").trim();
          if (!identTrim || !pwd) {
            mostrarPosToast("Ingrese supervisor y contraseña.");
            return;
          }
          const detalleId = pendingDetalleIdAutorizacionDesc;
          if (detalleId == null) return;
          pendingDetalleIdAutorizacionDesc = null;
          const modalInst = bootstrap.Modal.getInstance(modalAutorizaEl);
          if (modalInst) modalInst.hide();
          actualizarItem(detalleId, u.actualizar_item, {
            supervisor_identificador: identTrim,
            supervisor_clave: pwd,
          });
        });
      }
    }

    const supInputPos = document.getElementById("posSupervisorIdentificador");
    if (supInputPos) {
      supInputPos.addEventListener("input", posFiltrarMostrarSugerenciasSupervisor);
      supInputPos.addEventListener("focus", posFiltrarMostrarSugerenciasSupervisor);
    }

    function posSetRutObligatorioUi(obligatorio) {
      posRutObligatorioEnabled = !!obligatorio;
      if (rutToggleBtn) {
        rutToggleBtn.dataset.obligatorio = posRutObligatorioEnabled ? "1" : "0";
        rutToggleBtn.classList.toggle("is-on", posRutObligatorioEnabled);
        rutToggleBtn.classList.toggle("is-off", !posRutObligatorioEnabled);
      }
      if (rutToggleText) {
        rutToggleText.textContent = posRutObligatorioEnabled ? "RUT obligatorio" : "Sin RUT";
      }
      if (rutHintText) {
        rutHintText.textContent = posRutObligatorioEnabled
          ? "Fidelización activa: identifique al cliente."
          : "Cliente no quiso RUT — vale sin datos.";
      }
      const rutQuick = posRutQuickInput();
      if (rutQuick) {
        rutQuick.placeholder = posRutObligatorioEnabled ? "RUT cliente" : "RUT si lo entrega";
      }
      const idlePanel = document.getElementById("posClientePanelIdle");
      if (idlePanel) {
        const p = idlePanel.querySelector("p");
        if (p) {
          p.innerHTML = posRutObligatorioEnabled
            ? '<i class="fas fa-user me-1"></i>Identifique cliente (RUT) o use cliente final (F3).'
            : '<i class="fas fa-user me-1"></i>Venta sin datos — emite como cliente final si no hay RUT.';
        }
      }
      posSyncExigirRutHidden();
      if (!posRutObligatorioEnabled) aplicarClienteFinalSiRutOpcional();
    }

    async function posToggleRutObligatorio() {
      if (!u.rut_obligatorio_toggle || !rutToggleBtn) return;
      const next = !posRutObligatorioEnabled;
      rutToggleBtn.disabled = true;
      try {
        const res = await fetch(u.rut_obligatorio_toggle, {
          method: "POST",
          credentials: "same-origin",
          headers: {
            Accept: "application/json",
            "Content-Type": "application/json",
          },
          body: JSON.stringify({ obligatorio: next }),
        });
        const data = await res.json();
        if (!data.ok) throw new Error(data.error || "toggle");
        posSetRutObligatorioUi(data.obligatorio !== false);
        mostrarPosToast(
          posRutObligatorioEnabled
            ? "RUT obligatorio — fidelización activa."
            : "Sin RUT — vale sin datos de cliente."
        );
      } catch (_err) {
        mostrarPosToast("No se pudo cambiar la opción de RUT.");
      } finally {
        rutToggleBtn.disabled = false;
      }
    }

    if (crossSellToggleBtn) {
      posSetCrossSellUi(crossSellEnabled);
      crossSellToggleBtn.addEventListener("click", posToggleCrossSell);
    }
    if (rutToggleBtn) {
      posSetRutObligatorioUi(posRutObligatorioEnabled);
      rutToggleBtn.addEventListener("click", posToggleRutObligatorio);
    }

    function posFormatearRutInput(e) {
      let rut = e.target.value.replace(/\./g, "").replace(/-/g, "").toUpperCase();
      if (rut.length > 1) {
        const cuerpo = rut.slice(0, -1);
        const dv = rut.slice(-1);
        const cFmt = cuerpo.replace(/\B(?=(\d{3})+(?!\d))/g, ".");
        e.target.value = cFmt + "-" + dv;
      }
    }
    const rutQuick = posRutQuickInput();
    let posRutAutoLookupTimer = null;
    function clearPosRutAutoLookup() {
      if (posRutAutoLookupTimer) {
        clearTimeout(posRutAutoLookupTimer);
        posRutAutoLookupTimer = null;
      }
    }
    function rutQuickNormLen() {
      const raw = getClienteRutForSearch() || "";
      return raw.replace(/\./g, "").replace(/-/g, "").trim().length;
    }
    function schedulePosRutAutoLookup() {
      clearPosRutAutoLookup();
      posRutAutoLookupTimer = setTimeout(function () {
        posRutAutoLookupTimer = null;
        if (rutQuickNormLen() < 8) return;
        buscarClientePorRut(u.consultar_cliente);
      }, 420);
    }
    if (rutQuick) {
      rutQuick.addEventListener("input", posFormatearRutInput);
      rutQuick.addEventListener("input", schedulePosRutAutoLookup);
      rutQuick.addEventListener("keydown", function (e) {
        if (e.key !== "Enter") return;
        e.preventDefault();
        clearPosRutAutoLookup();
        buscarClientePorRut(u.consultar_cliente);
      });
    }

    const chkFinal = document.getElementById("cliente_final");
    if (chkFinal) {
      chkFinal.addEventListener("change", function () {
        syncClienteFinalMode(true);
      });
    }

    const formEmitir = document.getElementById("formEmitirVale");
    const puntoRetiroFormEl = document.getElementById("punto_retiro");
    const modalPuntoRetiroEl = document.getElementById("modalConfirmarPuntoRetiro");
    const modalPuntoRetiroSelect = document.getElementById("puntoRetiroModalSelect");
    const modalPuntoRetiroError = document.getElementById("puntoRetiroModalError");
    const btnConfirmarPuntoRetiro = document.getElementById("confirmarPuntoRetiroBtn");
    let submitConfirmadoDesdeModal = false;
    let modalPuntoRetiroInst = null;
    if (modalPuntoRetiroEl && typeof bootstrap !== "undefined") {
      modalPuntoRetiroInst = bootstrap.Modal.getOrCreateInstance(modalPuntoRetiroEl);
    }

    function sincronizarSelectPuntoRetiroEnModal() {
      if (!modalPuntoRetiroSelect || !puntoRetiroFormEl) return;
      modalPuntoRetiroSelect.value = (puntoRetiroFormEl.value || "__PENDIENTE__").trim() || "__PENDIENTE__";
      if (modalPuntoRetiroError) modalPuntoRetiroError.classList.add("d-none");
    }

    if (modalPuntoRetiroEl) {
      modalPuntoRetiroEl.addEventListener("shown.bs.modal", function () {
        if (modalPuntoRetiroSelect) modalPuntoRetiroSelect.focus();
      });
    }

    if (btnConfirmarPuntoRetiro) {
      btnConfirmarPuntoRetiro.addEventListener("click", function () {
        if (!modalPuntoRetiroSelect || !puntoRetiroFormEl || !formEmitir) return;
        const valor = (modalPuntoRetiroSelect.value || "").trim();
        if (!valor || valor === "__PENDIENTE__") {
          if (modalPuntoRetiroError) modalPuntoRetiroError.classList.remove("d-none");
          return;
        }
        puntoRetiroFormEl.value = valor;
        submitConfirmadoDesdeModal = true;
        if (modalPuntoRetiroInst) modalPuntoRetiroInst.hide();
        formEmitir.requestSubmit();
      });
    }

    if (formEmitir) {
      formEmitir.addEventListener("submit", function (e) {
        actualizarEstadoEmisionVale();
        if (document.getElementById("emitirValeBtn")?.disabled) {
          e.preventDefault();
          if (!puntoRetiroValido()) {
            mostrarPosToast("Seleccione punto de retiro antes de emitir.");
          } else {
            mostrarPosToast("Corrija items con stock insuficiente antes de emitir.");
          }
          return;
        }
        if (posValeEstaVacio()) {
          e.preventDefault();
          mostrarPosToast("Agregue al menos un producto (escanee o busque) antes de emitir el vale.");
          return;
        }
        syncHiddenClienteFromPanels();
        aplicarClienteFinalSiRutOpcional();
        if (!validarRutCliente()) {
          e.preventDefault();
          return;
        }
        if (!submitConfirmadoDesdeModal && !puntoRetiroValido()) {
          e.preventDefault();
          sincronizarSelectPuntoRetiroEnModal();
          if (modalPuntoRetiroInst) {
            modalPuntoRetiroInst.show();
          } else {
            mostrarPosToast("Seleccione punto de retiro antes de emitir.");
          }
          return;
        }
        submitConfirmadoDesdeModal = false;
      });
    }

    const wedge = document.getElementById("posBarcodeWedge");
    if (wedge) {
      wedge.addEventListener("keydown", function (e) {
        if (e.key !== "Enter") return;
        e.preventDefault();
        const codigo = (wedge.value || "").replace(/\r/g, "").replace(/\n/g, "").trim();
        wedge.value = "";
        if (!codigo) return;
        if (u.escanear_agregar) {
          posEscanearYAgregar(codigo, false);
        } else if (u.agregar_producto) {
          const form = document.createElement("form");
          form.method = "POST";
          form.action = u.agregar_producto;
          const inp = document.createElement("input");
          inp.type = "hidden";
          inp.name = "codigo";
          inp.value = codigo;
          form.appendChild(inp);
          document.body.appendChild(form);
          form.submit();
        }
      });
      wedge.focus();
    }

    const btnAltaProd = document.getElementById("posBtnAltaRapidaProducto");
    if (btnAltaProd) {
      btnAltaProd.addEventListener("click", function () {
        openPosProductoAltaRapidaModal(posUltimoCodigoEscaneado);
      });
    }
    const btnBuscarSim = document.getElementById("posBtnBuscarSimilar");
    if (btnBuscarSim) {
      btnBuscarSim.addEventListener("click", function () {
        if (posModalProductoNoEncontrado) posModalProductoNoEncontrado.hide();
        const term = posUltimoCodigoEscaneado || "";
        const inpManual = document.getElementById("posBuscarManual");
        if (inpManual) {
          inpManual.value = term;
          inpManual.focus();
          inpManual.dispatchEvent(new Event("input", { bubbles: true }));
        } else if ($("#buscarProducto").length) {
          const $sel = $("#buscarProducto");
          const opt = new Option(term, term, true, true);
          $sel.append(opt).trigger("change");
          $sel.select2("open");
        }
      });
    }
    const btnGuardarAlta = document.getElementById("posBtnGuardarAltaProducto");
    if (btnGuardarAlta) {
      btnGuardarAlta.addEventListener("click", guardarPosProductoAltaRapida);
    }

    let posManualSearchApi = null;
    const inpBuscarManual = document.getElementById("posBuscarManual");
    if (inpBuscarManual && u.buscar_producto) {
      posManualSearchApi = initPosManualSearch(u.buscar_producto);
    }

    const chkVend = document.getElementById("posSoloVendibles");
    function syncPosFiltroBusquedaBotones() {
      const bV = document.getElementById("posBtnFiltroVenta");
      const bC = document.getElementById("posBtnFiltroCatalogo");
      if (!chkVend || !bV || !bC) return;
      const strict = !!chkVend.checked;
      bV.classList.toggle("btn-primary", strict);
      bV.classList.toggle("btn-outline-secondary", !strict);
      bC.classList.toggle("btn-primary", !strict);
      bC.classList.toggle("btn-outline-secondary", strict);
    }
    function limpiarBusquedaManualPos() {
      if (inpBuscarManual) inpBuscarManual.value = "";
      if (posManualSearchApi && posManualSearchApi.hidePanel) posManualSearchApi.hidePanel();
    }
    if (chkVend) {
      chkVend.addEventListener("change", function () {
        syncPosFiltroBusquedaBotones();
        limpiarBusquedaManualPos();
        const term = inpBuscarManual ? (inpBuscarManual.value || "").trim() : "";
        if (term.length >= 3 && inpBuscarManual) {
          inpBuscarManual.dispatchEvent(new Event("input", { bubbles: true }));
        }
      });
    }
    const bVenta = document.getElementById("posBtnFiltroVenta");
    const bCat = document.getElementById("posBtnFiltroCatalogo");
    if (chkVend && bVenta && bCat) {
      bVenta.addEventListener("click", function () {
        chkVend.checked = true;
        chkVend.dispatchEvent(new Event("change"));
      });
      bCat.addEventListener("click", function () {
        chkVend.checked = false;
        chkVend.dispatchEvent(new Event("change"));
      });
      syncPosFiltroBusquedaBotones();
    }

    if ($("#buscarProducto").length && u.buscar_producto) {
      function posSoloVendiblesDeck() {
        const chk = document.getElementById("posSoloVendibles");
        return !!(chk && chk.checked);
      }
      $("#buscarProducto").select2({
        theme: "bootstrap-5",
        placeholder: "Buscar producto…",
        allowClear: true,
        minimumInputLength: 3,
        ajax: {
          url: u.buscar_producto,
          dataType: "json",
          delay: 280,
          data: function (params) {
            return {
              q: params.term || "",
              solo_vendibles: posSoloVendiblesDeck() ? "1" : "0",
              origen: "pos",
            };
          },
          processResults: function (data) {
            return { results: data && Array.isArray(data.results) ? data.results : [] };
          },
          cache: false,
        },
      });
      const hidPidDeck = document.getElementById("posSeleccionProductoId");
      $("#buscarProducto").on("select2:select", function (e) {
        const d = e.params && e.params.data;
        if (hidPidDeck && d && d.producto_id != null) hidPidDeck.value = String(d.producto_id);
      });
      $("#buscarProducto").on("select2:clear", function () {
        if (hidPidDeck) hidPidDeck.value = "";
      });
    }

    const sumLineas = posSumarSubtotalesFilasBrutas();
    let serverT = 0;
    const mtEl = document.getElementById("monto_total");
    if (mtEl) {
      const d = mtEl.getAttribute("data-pos-total-clp");
      if (d != null && String(d).trim() !== "") {
        serverT = parseInt(String(d).trim(), 10) || 0;
        if (isNaN(serverT)) serverT = 0;
      }
    }
    if (!serverT && mtEl) {
      serverT = Math.round(parseFloat(mtEl.textContent.replace(/[^0-9.-]/g, "")) || 0);
    }
    const totalInicial = Math.max(serverT, sumLineas);

    document.querySelectorAll("[id^='precio_unitario_']").forEach(function (cell) {
      const valor = parseFloat(cell.innerText) || 0;
      cell.innerText = formatoCLP(valor);
    });
    document.querySelectorAll("[id^='subtotal_']").forEach(function (cell) {
      const valor = parseFloat(cell.innerText) || 0;
      cell.innerText = formatoCLP(valor);
    });

    actualizarTotalesVisuales(totalInicial);

    posRefreshCrossSellPanel();

    initPosClienteUiFromConfig(cfg);
    if (cfg.cliente_vitrina) {
      renderPosTvClienteBadge(cfg.cliente_vitrina);
    }

    const btnGuardarClienteNuevo = document.getElementById("posBtnGuardarClienteNuevo");
    if (btnGuardarClienteNuevo) {
      btnGuardarClienteNuevo.addEventListener("click", function () {
        guardarPosClienteNuevoModal();
      });
    }
    const modalClienteNuevoEl = document.getElementById("modalPosClienteNuevo");
    if (modalClienteNuevoEl) {
      modalClienteNuevoEl.addEventListener("keydown", function (e) {
        if (e.key === "Enter" && e.target && e.target.id === "posClienteModalTelefono") {
          e.preventDefault();
          guardarPosClienteNuevoModal();
        }
      });
      modalClienteNuevoEl.addEventListener("hidden.bs.modal", function () {
        if (posClienteUiEstado !== "new") return;
        const nombre = document.getElementById("cliente_nombre");
        if (nombre && (nombre.value || "").trim()) return;
        setPosClienteUiState("idle");
      });
    }

    const btnCambiarCliente = document.getElementById("posBtnCambiarCliente");
    if (btnCambiarCliente) {
      btnCambiarCliente.addEventListener("click", function () {
        setClienteRutEverywhere("");
        ["cliente_nombre", "cliente_direccion", "cliente_giro", "cliente_comuna", "cliente_ciudad", "cliente_telefono", "cliente_correo"].forEach(function (id) {
          setHiddenClienteField(id, "");
        });
        const nn = document.getElementById("posClienteModalNombre");
        const nt = document.getElementById("posClienteModalTelefono");
        if (nn) nn.value = "";
        if (nt) nt.value = "";
        const chk = document.getElementById("cliente_final");
        if (chk) chk.checked = false;
        setPosClienteUiState("idle");
        vincularClienteEnVale({ limpiar: true }).then(function () {
          renderPosTvClienteBadge(null);
          posNotifyExperienceWallRefresh();
        });
      });
    }

    const btnIdentTv = document.getElementById("posBtnIdentificarTv");
    if (btnIdentTv) {
      btnIdentTv.addEventListener("click", function () {
        setClienteRutEverywhere(getClienteRutForSearch());
        buscarClientePorRut(u.consultar_cliente);
      });
    }
    const btnFinalTv = document.getElementById("posBtnClienteFinalTv");
    if (btnFinalTv) {
      btnFinalTv.addEventListener("click", function () {
        const chk = document.getElementById("cliente_final");
        if (chk) {
          chk.checked = true;
          syncClienteFinalMode(true);
        } else {
          vincularClienteEnVale({ cliente_final: true }).then(function (v) {
            if (v && v.ok) {
              renderPosTvClienteBadge(v.cliente_vitrina);
              posNotifyExperienceWallRefresh();
            }
          });
        }
      });
    }
    const btnQuitarTv = document.getElementById("posBtnQuitarClienteTv");
    if (btnQuitarTv) {
      btnQuitarTv.addEventListener("click", function () {
        const chk = document.getElementById("cliente_final");
        if (chk) chk.checked = false;
        setClienteRutEverywhere("");
        setPosClienteUiState("idle");
        vincularClienteEnVale({ limpiar: true }).then(function () {
          renderPosTvClienteBadge(null);
          posNotifyExperienceWallRefresh();
        });
      });
    }

    const buscarBtn = document.getElementById("buscarClienteBtn");
    if (buscarBtn) {
      buscarBtn.addEventListener("click", function () {
        buscarClientePorRut(u.consultar_cliente);
      });
    }
    if (rutQuick) {
      rutQuick.addEventListener("blur", function () {
        clearPosRutAutoLookup();
        if (rutQuickNormLen() >= 8) buscarClientePorRut(u.consultar_cliente);
      });
    }

    $(".cantidad-input").on("input change", function () {
      const detalleId = $(this).data("detalle-id");
      const precio = parseFloat($(this).data("precio")) || 0;
      actualizarSubtotal(detalleId, precio);
      actualizarEstadoEmisionVale();
      schedulePersistDetalle(detalleId, u.actualizar_item, true);
    });

    $(".descuento-input").on("input change", function () {
      const detalleId = $(this).data("detalle-id");
      const precio = parseFloat($(this).data("precio")) || 0;
      actualizarSubtotal(detalleId, precio);
      actualizarEstadoEmisionVale();
      // El descuento solo se guarda en servidor al pulsar "Actualizar" (así puede pedirse supervisor).
    });

    $(".btn-ajustar-cantidad").on("click", function () {
      const detalleId = parseInt($(this).data("detalle-id"), 10);
      const delta = parseInt($(this).data("delta"), 10);
      const precio = parseFloat($(this).data("precio")) || 0;
      ajustarCantidad(detalleId, delta, precio);
      actualizarEstadoEmisionVale();
      schedulePersistDetalle(detalleId, u.actualizar_item, true);
    });

    $(".btn-actualizar-item").on("click", function () {
      const detalleId = parseInt($(this).data("detalle-id"), 10);
      cancelPersistDetalle(detalleId);
      if (descuentoRequiereCredencialSupervisor(detalleId, descLibre)) {
        pendingDetalleIdAutorizacionDesc = detalleId;
        if (modalAutorizaEl && typeof bootstrap !== "undefined") {
          const modalInst = bootstrap.Modal.getOrCreateInstance(modalAutorizaEl);
          modalInst.show();
        } else {
          mostrarPosToast("No se pudo abrir la autorización. Recargue la página.");
        }
        return;
      }
      actualizarItem(detalleId, u.actualizar_item, {});
    });

    actualizarEstadoEmisionVale();

    const tbodyPos = document.querySelector(".table-ds tbody");
    if (tbodyPos) {
      tbodyPos.addEventListener("focusin", function (e) {
        const tr = e.target.closest("tr");
        if (!tr || !tbodyPos.contains(tr)) return;
        tbodyPos.querySelectorAll("tr.pos-row-active").forEach(function (r) {
          r.classList.remove("pos-row-active");
        });
        tr.classList.add("pos-row-active");
      });
    }

    document.querySelectorAll(".alert.alert-warning").forEach(function (alertEl) {
      const txt = (alertEl.textContent || "").replace(/\s+/g, " ").trim();
      const m = txt.match(/Producto no encontrado\s*\(([^)]+)\)/i);
      if (m) {
        alertEl.classList.add("d-none");
        openPosProductoNoEncontradoModal(m[1].trim(), []);
      }
    });

    document.addEventListener("keydown", function (e) {
      if (e.key === "F2") {
        e.preventDefault();
        const inp = document.getElementById("posBuscarManual");
        if (inp) {
          inp.focus();
          inp.select();
        } else if ($("#buscarProducto").length) {
          $("#buscarProducto").select2("open");
        }
      }
      if (e.key === "F3") {
        if (isTypingInField(e.target)) return;
        e.preventDefault();
        const chk = document.getElementById("cliente_final");
        if (!chk) return;
        chk.checked = !chk.checked;
        chk.dispatchEvent(new Event("change", { bubbles: true }));
      }
      if (e.key === "F4") {
        e.preventDefault();
        const btn = document.getElementById("emitirValeBtn");
        if (btn && !btn.disabled) btn.click();
        else if (posValeEstaVacio()) {
          mostrarPosToast("Agregue productos antes de emitir (F4).");
        }
      }
    });
  });
})();
