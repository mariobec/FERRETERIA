/**
 * Formulario cotización — búsqueda homologada con POS (semáforo, catálogo/operativo).
 */
(function () {
  const cfgEl = document.getElementById("cotFormConfig");
  if (!cfgEl) return;

  let cfg;
  try {
    cfg = JSON.parse(cfgEl.textContent || "{}");
  } catch (_e) {
    return;
  }

  const buscador = document.getElementById("buscadorProducto");
  const panel = document.getElementById("cotSearchSuggestions");
  const tbody = document.getElementById("tbodyLineas");
  const filaVacia = document.getElementById("filaVacia");
  const lineasCount = document.getElementById("lineasCount");
  const btnGuardar = document.getElementById("btnGuardar");
  const btnGuardarTop = document.getElementById("btnGuardarTop");
  const filtroBtns = document.querySelectorAll("[data-cot-filtro]");

  const fmt = (n) =>
    "$ " +
    Math.round(n || 0).toLocaleString("es-CL", { maximumFractionDigits: 0 });

  const ivaChile = typeof LhexiaIvaChile !== "undefined" ? LhexiaIvaChile : null;

  function roundHalfUp(value) {
    if (ivaChile && typeof ivaChile.roundHalfUp === "function") {
      return ivaChile.roundHalfUp(value);
    }
    const v = Number(value);
    if (!isFinite(v) || v <= 0) return 0;
    return Math.floor(v + 0.5);
  }

  function subtotalLineaClp(cant, pu, desc) {
    const c = parseCantidad(cant);
    const p = parseClpEntero(pu);
    const d = parseClpEntero(desc);
    return Math.max(0, roundHalfUp(c * p - d));
  }

  /** Cantidad (admite decimales). */
  function parseCantidad(val) {
    const s = String(val == null ? "" : val).trim().replace(",", ".");
    const n = parseFloat(s);
    return isFinite(n) ? n : 0;
  }

  /** Monto CLP entero: soporta 1849, 1.849, 16.639, 1.849.990 */
  function parseClpEntero(val) {
    let s = String(val == null ? "" : val).trim();
    if (!s) return 0;
    if (/^\d{1,3}(\.\d{3})+(,\d+)?$/.test(s) || /^\d{1,3}(\.\d{3})+$/.test(s)) {
      s = s.replace(/\./g, "");
    }
    s = s.replace(",", ".");
    const n = parseFloat(s);
    if (!isFinite(n)) return 0;
    return Math.max(0, roundHalfUp(n));
  }

  function totalesDesdeNetoClp(neto) {
    const n = Math.max(0, parseInt(neto, 10) || 0);
    if (n === 0) return { neto: 0, iva: 0, total: 0 };
    if (ivaChile && typeof ivaChile.ivaDesdeNetoClp === "function") {
      const iva = ivaChile.ivaDesdeNetoClp(n);
      return { neto: n, iva, total: n + iva };
    }
    const iva = roundHalfUp(n * 0.19);
    return { neto: n, iva, total: n + iva };
  }

  let filtroPos = "catalogo";
  let debounceTimer = null;
  let fetchCtrl = null;
  let activeIndex = -1;
  let lastItems = [];
  let lastQuery = "";

  function htmlLineaCodigoCol(it, esManual) {
    const pid = it.id || it.producto_id || "";
    const manual = esManual || !pid;
    if (manual) {
      return (
        '<input type="text" class="form-control form-control-sm cot-linea-codigo-input" name="det_codigo" value="' +
        escapeHtml(it.codigo || "") +
        '" placeholder="Ref." maxlength="80" autocomplete="off">'
      );
    }
    if (it.codigo) {
      return '<span class="cot-linea-articulo__cod">' + escapeHtml(it.codigo) + "</span>";
    }
    return '<span class="cot-linea-articulo__cod cot-linea-articulo__cod--empty">—</span>';
  }

  function htmlLineaArticuloCol(it, esManual) {
    const pid = it.id || it.producto_id || "";
    const nombreAttr = (it.nombre || "").replace(/"/g, "&quot;");
    if (esManual || !pid) {
      return (
        '<input type="hidden" name="det_producto_id" value="">' +
        '<div class="cot-linea-articulo cot-linea-articulo--manual">' +
        '<input type="text" class="form-control form-control-sm cot-linea-articulo__nom-input" name="det_nombre" value="' +
        escapeHtml(it.nombre || "") +
        '" placeholder="Descripción" required maxlength="200">' +
        '<span class="cot-linea-articulo__tag">Línea libre</span>' +
        "</div>"
      );
    }
    return (
      '<input type="hidden" name="det_producto_id" value="' +
      escapeHtml(String(pid)) +
      '">' +
      '<input type="hidden" name="det_codigo" value="' +
      escapeHtml(it.codigo || "") +
      '">' +
      '<input type="hidden" name="det_nombre" value="' +
      nombreAttr +
      '">' +
      '<div class="cot-linea-articulo__nom">' +
      escapeHtml(it.nombre) +
      "</div>"
    );
  }

  function htmlLineaProducto(it, esManual) {
    return htmlLineaArticuloCol(it, esManual);
  }

  function renumberLineas() {
    if (!tbody) return;
    let i = 0;
    tbody.querySelectorAll("tr.cot-linea-row").forEach((tr) => {
      i += 1;
      const num = tr.querySelector(".cot-linea-num-val");
      if (num) num.textContent = String(i);
    });
  }

  function setGuardarEnabled(enabled) {
    if (btnGuardar) btnGuardar.disabled = !enabled;
    if (btnGuardarTop) btnGuardarTop.disabled = !enabled;
  }

  function wireLineaRow(tr) {
    tr.classList.add("cot-linea-row");
    tr.querySelectorAll(".input-cant, .input-precio, .input-desc").forEach((inp) => {
      inp.addEventListener("input", recalcular);
      inp.addEventListener("change", recalcular);
    });
    const btnRem = tr.querySelector(".btn-remove");
    if (btnRem) {
      btnRem.addEventListener("click", () => {
        tr.remove();
        recalcular();
      });
    }
  }

  function actualizarCeldaSubtotal(tr, sub) {
    const cell = tr.querySelector(".cell-subtotal");
    if (!cell) return;
    cell.dataset.clp = String(sub);
    cell.textContent = fmt(sub);
    cell.title = "Cant × Precio neto − Dto = " + sub.toLocaleString("es-CL") + " CLP (neto)";
    tr.classList.toggle("cot-linea-row--warn", false);
  }

  function escapeHtml(s) {
    return String(s || "")
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  function semaforoClass(it) {
    const s = String((it && it.semaforo) || "").toLowerCase();
    if (s === "verde" || s === "amarillo" || s === "azul") {
      return " cot-search-card--semaforo-" + s;
    }
    return "";
  }

  function badgeHtml(badges) {
    if (!badges || !badges.length) return "";
    return badges
      .map((b) => {
        const t = String((b && b.tipo) || "").toLowerCase();
        const cls =
          t === "verde" || t === "amarillo" || t === "azul"
            ? " cot-search-badge--" + t
            : "";
        return (
          '<span class="cot-search-badge' +
          cls +
          '">' +
          escapeHtml(b.label || b.tipo || "") +
          "</span>"
        );
      })
      .join("");
  }

  function renderCard(it, idx) {
    const sem = String(it.semaforo || "verde").toLowerCase();
    const stT = it.stock_tienda != null ? it.stock_tienda : 0;
    const stB = it.stock_bodega != null ? it.stock_bodega : 0;
    const precio = it.precio_fmt || fmt(it.precio);
    return (
      '<div class="cot-search-card' +
      semaforoClass(it) +
      (activeIndex === idx ? " cot-search-card--active" : "") +
      '" data-idx="' +
      idx +
      '" role="option">' +
      '<span class="cot-semaforo-luz cot-semaforo-luz--' +
      sem +
      '" title="' +
      escapeHtml(it.semaforo_label || "") +
      '"></span>' +
      '<div class="flex-grow-1 min-w-0">' +
      '<div class="d-flex justify-content-between gap-2">' +
      '<strong class="text-truncate">' +
      escapeHtml(it.nombre) +
      "</strong>" +
      '<span class="text-nowrap fw-bold text-warning">' +
      escapeHtml(precio) +
      "</span>" +
      "</div>" +
      '<small class="text-muted">' +
      escapeHtml(it.codigo || "") +
      (it.marca ? " · " + escapeHtml(it.marca) : "") +
      " · Tienda " +
      stT +
      " · Bodega " +
      stB +
      "</small>" +
      '<div>' +
      badgeHtml(it.badges) +
      "</div>" +
      "</div></div>"
    );
  }

  function hidePanel() {
    if (!panel) return;
    panel.classList.add("d-none");
    panel.innerHTML = "";
    activeIndex = -1;
    lastItems = [];
  }

  function showPanel(items, queryText) {
    if (!panel) return;
    lastItems = items || [];
    const q = (queryText != null ? queryText : lastQuery || "").trim();
    if (!lastItems.length) {
      panel.innerHTML =
        '<div class="p-3">' +
        '<div class="text-muted small mb-2">Sin coincidencias en catálogo.</div>' +
        (q.length >= 2
          ? '<button type="button" class="btn btn-sm btn-outline-primary w-100" id="cotAddManualFromSearch">' +
            '<i class="fas fa-plus me-1"></i>Agregar «' +
            escapeHtml(q) +
            "» como línea libre</button>"
          : '<div class="small text-muted">Use el bloque <strong>Producto no catalogado</strong> abajo.</div>') +
        "</div>";
      panel.classList.remove("d-none");
      const btnManual = document.getElementById("cotAddManualFromSearch");
      if (btnManual) {
        btnManual.addEventListener("click", () => {
          agregarLinea(
            {
              nombre: q,
              codigo: "",
              precio: parseFloat(document.getElementById("cotManualPrecio")?.value || "0") || 0,
              cantidad: parseFloat(document.getElementById("cotManualCant")?.value || "1") || 1,
            },
            true
          );
          hidePanel();
          if (buscador) {
            buscador.value = "";
            buscador.focus();
          }
        });
      }
      return;
    }
    panel.innerHTML = lastItems.map((it, i) => renderCard(it, i)).join("");
    panel.classList.remove("d-none");
    panel.querySelectorAll(".cot-search-card").forEach((el) => {
      el.addEventListener("click", () => {
        const idx = parseInt(el.getAttribute("data-idx"), 10);
        if (!isNaN(idx)) seleccionarItem(idx);
      });
    });
  }

  function fetchProductos(q) {
    if (!cfg.buscar_productos) return;
    lastQuery = (q || "").trim();
    if (fetchCtrl) fetchCtrl.abort();
    fetchCtrl = new AbortController();
    const url =
      cfg.buscar_productos +
      "?q=" +
      encodeURIComponent(lastQuery) +
      "&filtro_pos=" +
      encodeURIComponent(filtroPos);
    fetch(url, { signal: fetchCtrl.signal })
      .then((r) => r.json())
      .then((data) => {
        const items = data.items || [];
        showPanel(items, lastQuery);
      })
      .catch((err) => {
        if (err && err.name === "AbortError") return;
        hidePanel();
      });
  }

  function seleccionarItem(idx) {
    const it = lastItems[idx];
    if (!it) return;
    agregarLinea(it);
    hidePanel();
    if (buscador) {
      buscador.value = "";
      buscador.focus();
    }
  }

  function agregarLinea(it, esManual) {
    if (filaVacia) filaVacia.remove();
    const tr = document.createElement("tr");
    const manual = esManual || !(it.id || it.producto_id);
    const cant = parseFloat(it.cantidad != null ? it.cantidad : 1) || 1;
    const precio = Math.round(it.precio || 0);
    tr.innerHTML =
      '<td class="cot-linea-num-cell"><span class="cot-linea-num-val">0</span></td>' +
      '<td class="cot-linea-codigo-cell">' +
      htmlLineaCodigoCol(it, manual) +
      "</td>" +
      '<td class="cot-linea-articulo-cell">' +
      htmlLineaArticuloCol(it, manual) +
      "</td>" +
      '<td class="text-end"><input type="number" min="0.01" step="0.01" value="' +
      cant +
      '" class="form-control form-control-sm input-cant cot-input-num" name="det_cantidad"></td>' +
      '<td class="text-end"><input type="number" min="0" step="1" value="' +
      precio +
      '" class="form-control form-control-sm input-precio cot-input-num" name="det_precio"></td>' +
      '<td class="text-end"><input type="number" min="0" step="1" value="0" class="form-control form-control-sm input-desc cot-input-num" name="det_descuento"></td>' +
      '<td class="text-end cot-linea-money cot-linea-money--total cell-subtotal" data-clp="0">$ 0</td>' +
      '<td class="text-end"><button type="button" class="btn btn-sm btn-outline-danger btn-remove cot-btn-icon" title="Quitar"><i class="fas fa-trash"></i></button></td>';
    tbody.appendChild(tr);
    wireLineaRow(tr);
    recalcular();
    if (!manual && cfg.cross_sell) setTimeout(checkCotCrossSell, 120);
  }

  function recalcular() {
    if (!tbody) return;
    let sumaNetoLineas = 0;
    const filas = tbody.querySelectorAll("tr.cot-linea-row");
    let n = 0;
    filas.forEach((tr) => {
      if (tr.id === "filaVacia") return;
      const cantInp = tr.querySelector(".input-cant");
      const puInp = tr.querySelector(".input-precio");
      if (!cantInp || !puInp) return;
      const cant = parseCantidad(cantInp.value);
      const pu = parseClpEntero(puInp.value);
      const desc = parseClpEntero(tr.querySelector(".input-desc")?.value);
      const sub = subtotalLineaClp(cant, pu, desc);
      actualizarCeldaSubtotal(tr, sub);
      sumaNetoLineas += sub;
      n += 1;
    });
    const descGlobal = parseClpEntero(
      document.getElementById("descuento_global")?.value
    );
    const neto = Math.max(0, roundHalfUp(sumaNetoLineas - descGlobal));
    const trib = totalesDesdeNetoClp(neto);
    const elSumaCol = document.getElementById("totSumaColumna");
    const elSumaLabel = document.getElementById("totSumaLabel");
    const elDescRow = document.getElementById("totDescGlobalRow");
    const elDesc = document.getElementById("totDescGlobal");
    const elNeto = document.getElementById("totNeto");
    const elIva = document.getElementById("totIva");
    const elTotal = document.getElementById("totTotal");
    if (elSumaCol) elSumaCol.textContent = fmt(sumaNetoLineas);
    if (elSumaLabel) elSumaLabel.textContent = "Suma neto (" + n + " líneas)";
    if (elDescRow && elDesc) {
      if (descGlobal > 0) {
        elDescRow.classList.remove("d-none");
        elDesc.textContent = "- " + fmt(descGlobal);
      } else {
        elDescRow.classList.add("d-none");
        elDesc.textContent = fmt(0);
      }
    }
    if (elNeto) elNeto.textContent = fmt(trib.neto);
    if (elIva) elIva.textContent = fmt(trib.iva);
    const elNetoIva = document.getElementById("totNetoIva");
    if (elNetoIva) elNetoIva.textContent = fmt(trib.total);
    if (elTotal) elTotal.textContent = fmt(trib.total);
    if (lineasCount) lineasCount.textContent = n + " líneas";
    setGuardarEnabled(n > 0);
    renumberLineas();
    updateOpcionesPreview();
  }

  function checkCotCrossSell() {
    const ids = [];
    tbody.querySelectorAll('input[name="det_producto_id"]').forEach((inp) => {
      const v = (inp.value || "").trim();
      if (v && /^\d+$/.test(v)) ids.push(v);
    });
    if (!ids.length || !cfg.cross_sell) return;
    fetch(cfg.cross_sell + "?producto_ids=" + encodeURIComponent(ids.join(",")))
      .then((r) => r.json())
      .then((data) => {
        const s = data.sugerencia;
        if (!s || !s.items || !s.items.length) return;
        const body = document.getElementById("cotCrossSellBody");
        const title = document.getElementById("cotCrossSellTitle");
        if (!body || !title) return;
        title.textContent = s.titulo || "Productos sugeridos";
        body.innerHTML =
          '<p class="small text-muted mb-2">' +
          escapeHtml(s.mensaje || "") +
          '</p><div class="d-flex flex-wrap gap-1" id="cotCrossSellBtns"></div>';
        const wrap = document.getElementById("cotCrossSellBtns");
        s.items.forEach((it) => {
          const b = document.createElement("button");
          b.type = "button";
          b.className = "btn btn-sm btn-outline-primary";
          b.textContent = "Agregar " + (it.nombre || "");
          b.addEventListener("click", () => {
            agregarLinea({
              id: it.id,
              nombre: it.nombre,
              codigo: it.codigo || "",
              precio: it.precio || 0,
              stock_tienda: 0,
              stock_bodega: 0,
            });
            const m = document.getElementById("cotCrossSellModal");
            if (m && typeof bootstrap !== "undefined") {
              bootstrap.Modal.getInstance(m)?.hide();
            }
          });
          wrap.appendChild(b);
        });
        const modalEl = document.getElementById("cotCrossSellModal");
        if (modalEl && typeof bootstrap !== "undefined") {
          bootstrap.Modal.getOrCreateInstance(modalEl).show();
        }
      })
      .catch(() => {});
  }

  if (buscador && panel) {
    buscador.addEventListener("input", () => {
      clearTimeout(debounceTimer);
      const q = buscador.value.trim();
      if (q.length < 2) {
        hidePanel();
        return;
      }
      debounceTimer = setTimeout(() => fetchProductos(q), 220);
    });

    buscador.addEventListener("keydown", (e) => {
      if (e.key === "ArrowDown" && lastItems.length) {
        e.preventDefault();
        activeIndex = Math.min(activeIndex + 1, lastItems.length - 1);
        showPanel(lastItems, lastQuery);
      } else if (e.key === "ArrowUp" && lastItems.length) {
        e.preventDefault();
        activeIndex = Math.max(activeIndex - 1, 0);
        showPanel(lastItems, lastQuery);
      } else if (e.key === "Enter") {
        if (activeIndex >= 0 && lastItems.length) {
          e.preventDefault();
          seleccionarItem(activeIndex);
        } else {
          const q = buscador.value.trim();
          if (q.length >= 2) {
            e.preventDefault();
            agregarLinea(
              {
                nombre: q,
                codigo: document.getElementById("cotManualCodigo")?.value.trim() || "",
                precio: parseFloat(document.getElementById("cotManualPrecio")?.value || "0") || 0,
                cantidad: parseFloat(document.getElementById("cotManualCant")?.value || "1") || 1,
              },
              true
            );
            hidePanel();
            buscador.value = "";
          }
        }
      } else if (e.key === "Escape") {
        hidePanel();
      }
    });

    document.addEventListener("click", (e) => {
      const hero = document.getElementById("cotSearchHero");
      if (hero && !hero.contains(e.target)) hidePanel();
    });
  }

  filtroBtns.forEach((btn) => {
    btn.addEventListener("click", () => {
      filtroBtns.forEach((b) => b.classList.remove("active"));
      btn.classList.add("active");
      filtroPos = btn.getAttribute("data-cot-filtro") || "catalogo";
      const q = buscador && buscador.value.trim();
      if (q && q.length >= 2) fetchProductos(q);
    });
  });

  const btnManualAgregar = document.getElementById("btnCotManualAgregar");
  const inpManualNombre = document.getElementById("cotManualNombre");
  const inpManualCodigo = document.getElementById("cotManualCodigo");
  const inpManualCant = document.getElementById("cotManualCant");
  const inpManualPrecio = document.getElementById("cotManualPrecio");

  function agregarDesdePanelManual() {
    const nombre = (inpManualNombre?.value || "").trim();
    if (!nombre) {
      inpManualNombre?.focus();
      return;
    }
    agregarLinea(
      {
        nombre,
        codigo: (inpManualCodigo?.value || "").trim(),
        cantidad: parseFloat(inpManualCant?.value || "1") || 1,
        precio: parseFloat(inpManualPrecio?.value || "0") || 0,
      },
      true
    );
    if (inpManualNombre) inpManualNombre.value = "";
    if (inpManualCodigo) inpManualCodigo.value = "";
    if (inpManualCant) inpManualCant.value = "1";
    inpManualNombre?.focus();
  }

  if (btnManualAgregar) btnManualAgregar.addEventListener("click", agregarDesdePanelManual);
  if (inpManualNombre) {
    inpManualNombre.addEventListener("keydown", (e) => {
      if (e.key === "Enter") {
        e.preventDefault();
        agregarDesdePanelManual();
      }
    });
  }

  const descGlobalHidden = document.getElementById("descuento_global");
  if (descGlobalHidden) descGlobalHidden.addEventListener("input", recalcular);

  const btnToggleManual = document.getElementById("btnToggleManual");
  const manualPanel = document.getElementById("cotManualLineaPanel");
  if (btnToggleManual && manualPanel) {
    btnToggleManual.addEventListener("click", () => {
      manualPanel.open = true;
      document.getElementById("cotManualNombre")?.focus();
    });
  }

  tbody.querySelectorAll("tr").forEach((tr) => {
    if (!tr.querySelector(".input-cant")) return;
    wireLineaRow(tr);
  });
  if (tbody) {
    recalcular();
  }

  // Cliente — modal + campos ocultos
  const buscadorCli = document.getElementById("buscadorCliente");
  const resultadosCli = document.getElementById("busqClientesResultados");
  const banner = document.getElementById("clienteSeleccionadoInfo");
  const banNombre = document.getElementById("clienteInfoNombre");
  const banCupo = document.getElementById("clienteInfoCupo");
  const banEstado = document.getElementById("clienteInfoEstado");
  const btnLimpiar = document.getElementById("btnLimpiarCliente");
  const btnAbrirCliente = document.getElementById("btnAbrirCliente");
  const clientPreviewEmpty = document.getElementById("cotClientPreviewEmpty");
  const clientPreviewFilled = document.getElementById("cotClientPreviewFilled");
  let timerCli = null;

  const clientFieldMap = [
    ["cliente_id", null],
    ["cliente_nombre", "modal_cliente_nombre"],
    ["cliente_rut", "modal_cliente_rut"],
    ["cliente_telefono", "modal_cliente_telefono"],
    ["cliente_giro", "modal_cliente_giro"],
    ["cliente_direccion", "modal_cliente_direccion"],
    ["cliente_comuna", "modal_cliente_comuna"],
    ["cliente_ciudad", "modal_cliente_ciudad"],
    ["cliente_correo", "modal_cliente_correo"],
  ];

  function getHidden(id) {
    return document.getElementById(id);
  }

  function syncModalFromHidden() {
    clientFieldMap.forEach(([hid, mid]) => {
      if (!mid) return;
      const h = getHidden(hid);
      const m = document.getElementById(mid);
      if (h && m) m.value = h.value || "";
    });
  }

  function syncHiddenFromModal() {
    clientFieldMap.forEach(([hid, mid]) => {
      if (!mid) return;
      const h = getHidden(hid);
      const m = document.getElementById(mid);
      if (h && m) h.value = (m.value || "").trim();
    });
    updateClientPreview();
  }

  function syncAllBeforeSave() {
    syncHiddenFromModal();
    const v = document.getElementById("modal_validez_dias");
    const d = document.getElementById("modal_descuento_global");
    const n = document.getElementById("modal_notas");
    const hv = getHidden("validez_dias");
    const hd = getHidden("descuento_global");
    const hn = getHidden("notas");
    if (hv && v) hv.value = v.value || "15";
    if (hd && d) hd.value = d.value || "0";
    if (hn && n) hn.value = n.value || "";
  }

  function htmlClientFichaRow(label, value, extraClass) {
    if (!value) return "";
    return (
      '<div class="cot-cliente-ficha__row">' +
      '<span class="cot-cliente-ficha__label">' +
      escapeHtml(label) +
      "</span>" +
      '<span class="cot-cliente-ficha__value' +
      (extraClass ? " " + extraClass : "") +
      '">' +
      escapeHtml(value) +
      "</span></div>"
    );
  }

  function buildDireccionCliente() {
    const dir = (getHidden("cliente_direccion")?.value || "").trim();
    const com = (getHidden("cliente_comuna")?.value || "").trim();
    const ciu = (getHidden("cliente_ciudad")?.value || "").trim();
    const parts = [];
    if (dir) parts.push(dir);
    if (com) parts.push(com);
    if (ciu) parts.push(ciu);
    return parts.join(", ");
  }

  function updateClientPreview() {
    const nombre = (getHidden("cliente_nombre")?.value || "").trim();
    const rut = (getHidden("cliente_rut")?.value || "").trim();
    const giro = (getHidden("cliente_giro")?.value || "").trim();
    const direccion = buildDireccionCliente();
    const tel = (getHidden("cliente_telefono")?.value || "").trim();
    const correo = (getHidden("cliente_correo")?.value || "").trim();
    const hasData = !!(nombre || rut || giro || direccion || tel || correo);

    if (clientPreviewEmpty) {
      clientPreviewEmpty.classList.toggle("d-none", hasData);
    }
    if (clientPreviewFilled) {
      clientPreviewFilled.classList.toggle("d-none", !hasData);
      if (hasData) {
        clientPreviewFilled.innerHTML =
          '<div class="cot-cliente-ficha__grid">' +
          '<div class="cot-cliente-ficha__col">' +
          htmlClientFichaRow("Nombre", nombre, "cot-cliente-ficha__value--nombre") +
          htmlClientFichaRow("RUT", rut) +
          htmlClientFichaRow("Giro", giro) +
          htmlClientFichaRow("Dirección", direccion) +
          "</div>" +
          '<div class="cot-cliente-ficha__col cot-cliente-ficha__col--contacto">' +
          htmlClientFichaRow("Teléfono", tel) +
          htmlClientFichaRow("Correo", correo, "cot-cliente-ficha__value--email") +
          "</div></div>";
      } else {
        clientPreviewFilled.innerHTML = "";
      }
    }
    if (btnAbrirCliente) {
      btnAbrirCliente.classList.toggle("btn-outline-warning", hasData);
      btnAbrirCliente.classList.toggle("btn-outline-secondary", !hasData);
    }
  }

  function updateClientChip() {
    updateClientPreview();
  }

  function updateOpcionesPreview() {
    const validez = parseInt(getHidden("validez_dias")?.value || "15", 10) || 15;
    const notas = (getHidden("notas")?.value || "").trim();
    const elVal = document.getElementById("cotValidezPreview");
    const elNotas = document.getElementById("cotNotasPreviewText");
    if (elVal) elVal.textContent = "Validez: " + validez + " días";
    if (elNotas) {
      elNotas.textContent = notas || "Sin notas — edite en «Validez · Notas»";
      elNotas.classList.toggle("text-muted", !notas);
      elNotas.classList.toggle("fst-italic", !notas);
    }
  }

  function syncOpcionesFromModal() {
    const v = document.getElementById("modal_validez_dias");
    const d = document.getElementById("modal_descuento_global");
    const n = document.getElementById("modal_notas");
    const hv = getHidden("validez_dias");
    const hd = getHidden("descuento_global");
    const hn = getHidden("notas");
    if (hv && v) hv.value = v.value || "15";
    if (hd && d) hd.value = d.value || "0";
    if (hn && n) hn.value = n.value || "";
    updateOpcionesPreview();
    recalcular();
  }

  function syncOpcionesToModal() {
    const v = document.getElementById("modal_validez_dias");
    const d = document.getElementById("modal_descuento_global");
    const n = document.getElementById("modal_notas");
    if (v) v.value = getHidden("validez_dias")?.value || "15";
    if (d) d.value = getHidden("descuento_global")?.value || "0";
    if (n) n.value = getHidden("notas")?.value || "";
  }

  const btnOpcionesListo = document.getElementById("btnOpcionesListo");
  if (btnOpcionesListo) btnOpcionesListo.addEventListener("click", syncOpcionesFromModal);

  const modalOpciones = document.getElementById("modalOpcionesCot");
  if (modalOpciones) {
    modalOpciones.addEventListener("show.bs.modal", syncOpcionesToModal);
  }

  const modalCliente = document.getElementById("modalClienteCot");
  if (modalCliente) {
    modalCliente.addEventListener("show.bs.modal", () => {
      syncModalFromHidden();
      if (buscadorCli) {
        buscadorCli.value = "";
        setTimeout(() => buscadorCli.focus(), 180);
      }
      if (resultadosCli) {
        resultadosCli.style.display = "none";
        resultadosCli.innerHTML = "";
      }
    });
    modalCliente.addEventListener("hide.bs.modal", syncHiddenFromModal);
  }

  const btnClienteListo = document.getElementById("btnClienteListo");
  if (btnClienteListo) {
    btnClienteListo.addEventListener("click", syncHiddenFromModal);
  }

  const formCot = document.getElementById("formCotizacion");
  if (formCot) {
    formCot.addEventListener("submit", syncAllBeforeSave);
  }

  function strClienteCot(v) {
    if (v == null || v === "") return "";
    const s = String(v).trim();
    if (!s || /^(none|null|undefined|nan)$/i.test(s)) return "";
    return s;
  }

  function rellenarCliente(c) {
    const idEl = getHidden("cliente_id");
    if (idEl) idEl.value = c.id || "";
    const fields = {
      modal_cliente_nombre: strClienteCot(c.nombre),
      modal_cliente_rut: strClienteCot(c.rut),
      modal_cliente_telefono: strClienteCot(c.telefono),
      modal_cliente_giro: strClienteCot(c.giro),
      modal_cliente_direccion: strClienteCot(c.direccion),
      modal_cliente_comuna: strClienteCot(c.comuna),
      modal_cliente_ciudad: strClienteCot(c.ciudad),
      modal_cliente_correo: strClienteCot(c.correo),
    };
    Object.keys(fields).forEach((id) => {
      const el = document.getElementById(id);
      if (el) el.value = fields[id];
    });
    syncHiddenFromModal();
    if (banNombre) banNombre.textContent = c.nombre || "";
    if (banCupo) banCupo.textContent = fmt(c.cupo_disponible || 0);
    if (banEstado) {
      banEstado.textContent = c.estado_credito || "Activo";
      banEstado.className =
        "badge ms-2 " + (c.estado_credito === "Bloqueado" ? "bg-danger" : "bg-success");
    }
    if (banner) banner.classList.remove("d-none");
    if (btnLimpiar) btnLimpiar.classList.remove("d-none");
  }

  function limpiarCliente() {
    clientFieldMap.forEach(([hid, mid]) => {
      const h = getHidden(hid);
      if (h) h.value = "";
      if (mid) {
        const m = document.getElementById(mid);
        if (m) m.value = "";
      }
    });
    if (banner) banner.classList.add("d-none");
    if (btnLimpiar) btnLimpiar.classList.add("d-none");
    if (buscadorCli) buscadorCli.value = "";
    if (resultadosCli) {
      resultadosCli.style.display = "none";
      resultadosCli.innerHTML = "";
    }
    updateClientChip();
  }

  if (btnLimpiar) btnLimpiar.addEventListener("click", limpiarCliente);

  if (buscadorCli && resultadosCli) {
    if (!cfg.buscar_clientes) {
      buscadorCli.placeholder = "Búsqueda no disponible — ingrese datos manualmente abajo.";
      buscadorCli.disabled = true;
    } else {
    buscadorCli.addEventListener("input", () => {
      clearTimeout(timerCli);
      const q = buscadorCli.value.trim();
      if (q.length < 2) {
        resultadosCli.style.display = "none";
        resultadosCli.innerHTML = "";
        return;
      }
      timerCli = setTimeout(() => {
        fetch(cfg.buscar_clientes + "?q=" + encodeURIComponent(q))
          .then((r) => r.json())
          .then((data) => {
            resultadosCli.innerHTML = "";
            if (!data.items || !data.items.length) {
              resultadosCli.innerHTML =
                '<div class="list-group-item text-muted small">Sin coincidencias. Puede ingresar datos manualmente.</div>';
            } else {
              data.items.forEach((c) => {
                const a = document.createElement("a");
                a.href = "#";
                a.className = "list-group-item list-group-item-action";
                const credColor =
                  c.estado_credito === "Bloqueado" ? "text-danger" : "text-success";
                a.innerHTML =
                  '<div class="d-flex justify-content-between">' +
                  "<strong>" +
                  escapeHtml(c.nombre) +
                  "</strong>" +
                  '<small class="' +
                  credColor +
                  '">' +
                  escapeHtml(c.estado_credito || "Activo") +
                  " · cupo " +
                  fmt(c.cupo_disponible || 0) +
                  "</small></div>" +
                  '<small class="text-muted">' +
                  escapeHtml(c.rut || "s/RUT") +
                  " · " +
                  escapeHtml(c.telefono || "s/tel") +
                  "</small>";
                a.addEventListener("click", (e) => {
                  e.preventDefault();
                  rellenarCliente(c);
                  resultadosCli.style.display = "none";
                  buscadorCli.value = "";
                });
                resultadosCli.appendChild(a);
              });
            }
            resultadosCli.style.display = "block";
          })
          .catch(() => {
            resultadosCli.style.display = "none";
          });
      }, 220);
    });

    document.addEventListener("click", (e) => {
      if (!resultadosCli.contains(e.target) && e.target !== buscadorCli) {
        resultadosCli.style.display = "none";
      }
    });
    }
  }

  clientFieldMap.forEach(([hid, mid]) => {
    if (!mid) return;
    const m = document.getElementById(mid);
    if (!m) return;
    m.addEventListener("input", () => {
      const h = getHidden(hid);
      if (h) h.value = (m.value || "").trim();
      if (hid === "cliente_nombre" || hid === "cliente_rut") {
        const idEl = getHidden("cliente_id");
        if (idEl && idEl.value) {
          idEl.value = "";
          if (banner) banner.classList.add("d-none");
          if (btnLimpiar) btnLimpiar.classList.add("d-none");
        }
      }
      updateClientPreview();
    });
  });

  syncModalFromHidden();
  updateClientChip();
  updateOpcionesPreview();
  renumberLineas();

  if ((getHidden("cliente_id")?.value || getHidden("cliente_nombre")?.value) && btnLimpiar) {
    btnLimpiar.classList.remove("d-none");
  }
  if (getHidden("cliente_nombre")?.value && banNombre && banner) {
    banNombre.textContent = getHidden("cliente_nombre").value;
    banner.classList.remove("d-none");
  }
})();
