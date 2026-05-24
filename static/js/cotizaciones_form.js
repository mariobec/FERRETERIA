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
  const filtroBtns = document.querySelectorAll("[data-cot-filtro]");

  const fmt = (n) =>
    "$ " +
    Math.round(n || 0).toLocaleString("es-CL", { maximumFractionDigits: 0 });

  let filtroPos = "catalogo";
  let debounceTimer = null;
  let fetchCtrl = null;
  let activeIndex = -1;
  let lastItems = [];

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

  function showPanel(items) {
    if (!panel) return;
    lastItems = items || [];
    if (!lastItems.length) {
      panel.innerHTML =
        '<div class="p-3 text-muted small">Sin coincidencias. Pruebe otro término o filtro.</div>';
      panel.classList.remove("d-none");
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
    if (fetchCtrl) fetchCtrl.abort();
    fetchCtrl = new AbortController();
    const url =
      cfg.buscar_productos +
      "?q=" +
      encodeURIComponent(q) +
      "&filtro_pos=" +
      encodeURIComponent(filtroPos);
    fetch(url, { signal: fetchCtrl.signal })
      .then((r) => r.json())
      .then((data) => {
        const items = data.items || [];
        showPanel(items);
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

  function agregarLinea(it) {
    if (filaVacia) filaVacia.remove();
    const tr = document.createElement("tr");
    const pid = it.id || it.producto_id || "";
    const nombre = (it.nombre || "").replace(/"/g, "&quot;");
    tr.innerHTML =
      "<td>" +
      '<input type="hidden" name="det_producto_id" value="' +
      escapeHtml(String(pid)) +
      '">' +
      '<input type="hidden" name="det_codigo" value="' +
      escapeHtml(it.codigo || "") +
      '">' +
      "<div><strong>" +
      escapeHtml(it.nombre) +
      "</strong></div>" +
      '<small class="text-muted">' +
      escapeHtml(it.codigo || "") +
      (it.semaforo_label
        ? ' · <span class="text-success">' + escapeHtml(it.semaforo_label) + "</span>"
        : "") +
      "</small>" +
      '<input type="hidden" name="det_nombre" value="' +
      nombre +
      '">' +
      "</td>" +
      '<td><input type="number" min="0.01" step="0.01" value="1" class="form-control form-control-sm input-cant" name="det_cantidad"></td>' +
      '<td><input type="number" min="0" step="1" value="' +
      Math.round(it.precio || 0) +
      '" class="form-control form-control-sm input-precio" name="det_precio"></td>' +
      '<td><input type="number" min="0" step="1" value="0" class="form-control form-control-sm input-desc" name="det_descuento"></td>' +
      '<td class="text-end fw-bold cell-subtotal">' +
      fmt(it.precio || 0) +
      "</td>" +
      '<td class="text-end"><button type="button" class="btn btn-sm btn-outline-danger btn-remove" title="Quitar"><i class="fas fa-trash"></i></button></td>';
    tbody.appendChild(tr);
    tr.querySelectorAll(".input-cant, .input-precio, .input-desc").forEach((inp) => {
      inp.addEventListener("input", recalcular);
    });
    tr.querySelector(".btn-remove").addEventListener("click", () => {
      tr.remove();
      recalcular();
    });
    recalcular();
    if (cfg.cross_sell) setTimeout(checkCotCrossSell, 120);
  }

  function recalcular() {
    let bruto = 0;
    const filas = tbody.querySelectorAll("tr");
    let n = 0;
    filas.forEach((tr) => {
      if (!tr.querySelector(".input-cant")) return;
      const cant = parseFloat(tr.querySelector(".input-cant")?.value || "0");
      const pu = parseFloat(tr.querySelector(".input-precio")?.value || "0");
      const desc = parseFloat(tr.querySelector(".input-desc")?.value || "0");
      const sub = Math.max(0, cant * pu - desc);
      const cell = tr.querySelector(".cell-subtotal");
      if (cell) cell.textContent = fmt(sub);
      if (!isNaN(cant)) {
        bruto += sub;
        n++;
      }
    });
    const descGlobal = parseFloat(
      document.querySelector('input[name="descuento_global"]')?.value || "0"
    );
    bruto = Math.max(0, bruto - descGlobal);
    const neto = Math.round(bruto / 1.19);
    const iva = Math.round(bruto - neto);
    const total = neto + iva;
    const elBruto = document.getElementById("totBruto");
    const elNeto = document.getElementById("totNeto");
    const elIva = document.getElementById("totIva");
    const elTotal = document.getElementById("totTotal");
    if (elBruto) elBruto.textContent = fmt(bruto + descGlobal);
    if (elNeto) elNeto.textContent = fmt(neto);
    if (elIva) elIva.textContent = fmt(iva);
    if (elTotal) elTotal.textContent = fmt(total);
    if (lineasCount) lineasCount.textContent = n + " líneas";
    if (btnGuardar) btnGuardar.disabled = n === 0;
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
      if (!lastItems.length) return;
      if (e.key === "ArrowDown") {
        e.preventDefault();
        activeIndex = Math.min(activeIndex + 1, lastItems.length - 1);
        showPanel(lastItems);
      } else if (e.key === "ArrowUp") {
        e.preventDefault();
        activeIndex = Math.max(activeIndex - 1, 0);
        showPanel(lastItems);
      } else if (e.key === "Enter" && activeIndex >= 0) {
        e.preventDefault();
        seleccionarItem(activeIndex);
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

  const descGlobal = document.querySelector('input[name="descuento_global"]');
  if (descGlobal) descGlobal.addEventListener("input", recalcular);

  tbody.querySelectorAll("tr").forEach((tr) => {
    if (!tr.querySelector(".input-cant")) return;
    tr.querySelectorAll(".input-cant, .input-precio, .input-desc").forEach((inp) => {
      if (inp) inp.addEventListener("input", recalcular);
    });
    const btnRem = tr.querySelector(".btn-remove");
    if (btnRem) btnRem.addEventListener("click", () => { tr.remove(); recalcular(); });
  });
  recalcular();

  // Cliente (sin cambios de lógica)
  const buscadorCli = document.getElementById("buscadorCliente");
  const resultadosCli = document.getElementById("busqClientesResultados");
  const banner = document.getElementById("clienteSeleccionadoInfo");
  const banNombre = document.getElementById("clienteInfoNombre");
  const banCupo = document.getElementById("clienteInfoCupo");
  const banEstado = document.getElementById("clienteInfoEstado");
  const btnLimpiar = document.getElementById("btnLimpiarCliente");
  let timerCli = null;

  function strClienteCot(v) {
    if (v == null || v === "") return "";
    const s = String(v).trim();
    if (!s || /^(none|null|undefined|nan)$/i.test(s)) return "";
    return s;
  }

  function rellenarCliente(c) {
    document.getElementById("cliente_id").value = c.id || "";
    document.getElementById("cliente_nombre").value = strClienteCot(c.nombre);
    document.getElementById("cliente_rut").value = strClienteCot(c.rut);
    document.getElementById("cliente_telefono").value = strClienteCot(c.telefono);
    document.getElementById("cliente_giro").value = strClienteCot(c.giro);
    document.getElementById("cliente_direccion").value = strClienteCot(c.direccion);
    document.getElementById("cliente_comuna").value = strClienteCot(c.comuna);
    document.getElementById("cliente_ciudad").value = strClienteCot(c.ciudad);
    document.getElementById("cliente_correo").value = strClienteCot(c.correo);
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
    [
      "cliente_id",
      "cliente_nombre",
      "cliente_rut",
      "cliente_telefono",
      "cliente_giro",
      "cliente_direccion",
      "cliente_comuna",
      "cliente_ciudad",
      "cliente_correo",
    ].forEach((id) => {
      const el = document.getElementById(id);
      if (el) el.value = "";
    });
    if (banner) banner.classList.add("d-none");
    if (btnLimpiar) btnLimpiar.classList.add("d-none");
    if (buscadorCli) buscadorCli.value = "";
    if (resultadosCli) {
      resultadosCli.style.display = "none";
      resultadosCli.innerHTML = "";
    }
  }

  if (btnLimpiar) btnLimpiar.addEventListener("click", limpiarCliente);

  if (buscadorCli && resultadosCli && cfg.buscar_clientes) {
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

  ["cliente_nombre", "cliente_rut"].forEach((id) => {
    const el = document.getElementById(id);
    if (!el) return;
    el.addEventListener("input", () => {
      const idEl = document.getElementById("cliente_id");
      if (idEl && idEl.value) {
        idEl.value = "";
        if (banner) banner.classList.add("d-none");
        if (btnLimpiar) btnLimpiar.classList.add("d-none");
      }
    });
  });
})();
