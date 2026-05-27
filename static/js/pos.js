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

  function posEsBusquedaUnificada() {
    return !!document.querySelector(".pos-unified-search-hero");
  }

  function posInputBusqueda() {
    return document.getElementById("posBuscarManual");
  }

  function posInputEscaner() {
    return document.getElementById("posBarcodeWedge") || posInputBusqueda();
  }

  function posPareceCodigoBarras(q) {
    const s = (q || "").trim();
    if (!s || s.length > 60) return false;
    return !/\s/.test(s);
  }

  /** Después de validar RUT contra el servidor, devuelve el foco al lector / escáner de productos. */
  function posFocusBarcodeWedgeSoon() {
    requestAnimationFrame(function () {
      setTimeout(function () {
        const wedge = posInputEscaner();
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

  /** Entero CLP desde texto con $ y miles con punto (ej. "$26.805" → 26805). */
  function posParseClpText(text) {
    const digits = String(text || "").replace(/[^\d]/g, "");
    if (!digits) return 0;
    const n = parseInt(digits, 10);
    return isNaN(n) ? 0 : Math.max(0, n);
  }

  function posReadClpFromEl(el) {
    if (!el) return 0;
    const attr = el.getAttribute("data-clp");
    if (attr != null && String(attr).trim() !== "") {
      const n = parseInt(String(attr).trim(), 10);
      if (!isNaN(n)) return Math.max(0, n);
    }
    return posParseClpText(el.textContent || el.innerText);
  }

  function posWriteClpToEl(el, amount, suffix) {
    if (!el) return;
    const n = Math.round(amount || 0);
    el.setAttribute("data-clp", String(n));
    el.textContent = formatoCLP(n) + (suffix || "");
  }

  function posContarLineasValeDom() {
    const filas = document.querySelectorAll("[id^='pos_row_']");
    if (filas.length) return filas.length;
    return document.querySelectorAll(".cantidad-input").length;
  }

  function posDescuentoPctDesdeInput(detalleId) {
    const el = document.getElementById("descuento_" + detalleId);
    if (!el) return 0;
    const raw = String(el.value || "").trim();
    if (!raw) return 0;
    const n = parseFloat(raw);
    if (!Number.isFinite(n)) return 0;
    return Math.max(0, Math.min(100, n));
  }

  function posDescuentoValorParaServidor(detalleId) {
    const n = posDescuentoPctDesdeInput(detalleId);
    const el = document.getElementById("descuento_" + detalleId);
    if (el) {
      el.value = n > 0 ? String(Math.round(n * 100) / 100) : "";
    }
    return String(n);
  }

  function posSyncDtoChip(detalleId) {
    const inp = document.getElementById("descuento_" + detalleId);
    const chip = document.getElementById("descuento_chip_" + detalleId);
    if (!inp) return;
    const v = Math.round(parseFloat(inp.value) || 0);
    if (chip) chip.textContent = String(v) + "%";
    const det = inp.closest(".pos-cart-card__more");
    if (det) det.classList.toggle("pos-cart-card__more--active", v > 0);
  }

  function posFocusDescuentoInput(detalleId) {
    const inp = document.getElementById("descuento_" + detalleId);
    if (!inp) return;
    requestAnimationFrame(function () {
      try {
        inp.focus({ preventScroll: true });
      } catch (_e) {
        inp.focus();
      }
      try {
        inp.select();
      } catch (_e2) {
        /* ignore */
      }
    });
  }

  function posCerrarMenuDto(detalleId) {
    const row = document.getElementById("pos_row_" + detalleId);
    const det = row && row.querySelector(".pos-cart-card__more");
    if (det) det.open = false;
    if (row) row.classList.remove("pos-cart-card--dto-open");
  }

  function posCerrarTodosMenusDto() {
    document.querySelectorAll(".pos-cart-card__more[open]").forEach(function (det) {
      det.open = false;
    });
    document.querySelectorAll(".pos-cart-card--dto-open").forEach(function (card) {
      card.classList.remove("pos-cart-card--dto-open");
    });
  }

  function posAplicarDescuentoRapido(detalleId, pct, descLibre, urlActualizarItem) {
    const inp = document.getElementById("descuento_" + detalleId);
    if (!inp) return;
    const p = Math.max(0, Math.min(100, parseInt(pct, 10) || 0));
    inp.value = String(p);
    const precio = parseFloat(inp.dataset.precio) || 0;
    actualizarSubtotal(detalleId, precio);
    actualizarEstadoEmisionVale();
    posSyncDtoChip(detalleId);
    posCerrarMenuDto(detalleId);
    cancelPersistDetalle(detalleId);
    posIntentarGuardarLineaConAutorizacionDesc(detalleId, descLibre, urlActualizarItem, {
      cerrar_menu: true,
    });
  }

  var POS_SCROLL_KEY = "pos_scroll_y";
  var POS_RESTORE_UI_KEY = "pos_restore_ui";

  function posScrollGuardar() {
    if (document.body.classList.contains("pos-pantalla-vendedora")) return;
    try {
      sessionStorage.setItem(POS_SCROLL_KEY, String(window.scrollY || 0));
      sessionStorage.setItem(POS_RESTORE_UI_KEY, "1");
    } catch (_e) {
      /* ignore */
    }
  }

  function posScrollRestaurar() {
    if (document.body.classList.contains("pos-pantalla-vendedora")) {
      try {
        sessionStorage.removeItem(POS_RESTORE_UI_KEY);
        sessionStorage.removeItem(POS_SCROLL_KEY);
      } catch (_e) {
        /* ignore */
      }
      return;
    }
    try {
      if (sessionStorage.getItem(POS_RESTORE_UI_KEY) !== "1") return;
      sessionStorage.removeItem(POS_RESTORE_UI_KEY);
      var y = parseInt(sessionStorage.getItem(POS_SCROLL_KEY) || "0", 10);
      sessionStorage.removeItem(POS_SCROLL_KEY);
      if (isNaN(y) || y <= 0) return;
      requestAnimationFrame(function () {
        requestAnimationFrame(function () {
          window.scrollTo(0, y);
          var inp = posInputBusqueda();
          if (inp) {
            try {
              inp.focus({ preventScroll: true });
            } catch (_e2) {
              inp.focus();
            }
          }
        });
      });
    } catch (_e) {
      /* ignore */
    }
  }

  function posPanelScrollToCard(panelEl, cardEl) {
    if (!panelEl || !cardEl) return;
    var panelRect = panelEl.getBoundingClientRect();
    var cardRect = cardEl.getBoundingClientRect();
    if (cardRect.top < panelRect.top) {
      panelEl.scrollTop -= panelRect.top - cardRect.top + 8;
    } else if (cardRect.bottom > panelRect.bottom) {
      panelEl.scrollTop += cardRect.bottom - panelRect.bottom + 8;
    }
  }

  function posFiltroBusquedaActual() {
    const hid = document.getElementById("posFiltroBusqueda");
    const v = hid ? String(hid.value || "").trim().toLowerCase() : "";
    if (v === "operativo" || v === "tienda" || v === "catalogo") return v;
    return "operativo";
  }

  function setPosFiltroBusqueda(modo) {
    const hid = document.getElementById("posFiltroBusqueda");
    if (hid) hid.value = modo;
  }

  function syncPosFiltroBusquedaBotones() {
    const modo = posFiltroBusquedaActual();
    const pills = document.querySelectorAll(".pos-filter-pill[data-filter]");
    pills.forEach(function (btn) {
      const f = (btn.getAttribute("data-filter") || "").trim();
      btn.classList.toggle("pos-filter-pill--active", f === modo);
    });
    const bOp = document.getElementById("posBtnFiltroOperativo");
    const bTi = document.getElementById("posBtnFiltroTienda");
    const bCat = document.getElementById("posBtnFiltroCatalogo");
    if (bOp) {
      bOp.classList.toggle("btn-primary", modo === "operativo");
      bOp.classList.toggle("btn-outline-secondary", modo !== "operativo");
    }
    if (bTi) {
      bTi.classList.toggle("btn-primary", modo === "tienda");
      bTi.classList.toggle("btn-outline-secondary", modo !== "tienda");
    }
    if (bCat) {
      bCat.classList.toggle("btn-primary", modo === "catalogo");
      bCat.classList.toggle("btn-outline-secondary", modo !== "catalogo");
    }
  }

  function aplicarPosFiltroBusqueda(modo, posManualSearchApi) {
    setPosFiltroBusqueda(modo);
    syncPosFiltroBusquedaBotones();
    const inp = document.getElementById("posBuscarManual");
    const q = inp ? String(inp.value || "").trim() : "";
    if (q.length >= 2) {
      inp.dispatchEvent(new Event("input", { bubbles: true }));
      return;
    }
    if (inp) inp.value = "";
    if (posManualSearchApi && posManualSearchApi.hidePanel) {
      posManualSearchApi.hidePanel();
    }
  }

  function wirePosFiltroBusquedaBotones(posManualSearchApi) {
    const bOperativo = document.getElementById("posBtnFiltroOperativo");
    const bTienda = document.getElementById("posBtnFiltroTienda");
    const bCatalogo = document.getElementById("posBtnFiltroCatalogo");
    const hidFiltro = document.getElementById("posFiltroBusqueda");
    if (bOperativo) {
      bOperativo.addEventListener("click", function () {
        aplicarPosFiltroBusqueda("operativo", posManualSearchApi);
      });
    }
    if (bTienda) {
      bTienda.addEventListener("click", function () {
        aplicarPosFiltroBusqueda("tienda", posManualSearchApi);
      });
    }
    if (bCatalogo) {
      bCatalogo.addEventListener("click", function () {
        aplicarPosFiltroBusqueda("catalogo", posManualSearchApi);
      });
    }
    if (hidFiltro && !String(hidFiltro.value || "").trim()) {
      setPosFiltroBusqueda("operativo");
    }
    syncPosFiltroBusquedaBotones();
  }

  function wirePosPedidosApedido(urls) {
    const listEl = document.getElementById("posPedidosApedidoList");
    const panelEl = document.getElementById("posPedidosApedidoPanel");
    const baseUrl = urls && urls.pedidos_apedido;
    if (!listEl || !baseUrl) return;

    if (panelEl) posAnclarModalEnBody(panelEl);

    let filtroActivo = "abiertos";

    function pedidoEstadoUrl(id) {
      return String(baseUrl).replace(/\/?$/, "") + "/" + encodeURIComponent(String(id)) + "/estado";
    }

    function posRenderPedidosResumen(resumen) {
      const box = document.getElementById("posPedidosApedidoResumen");
      const badge = document.getElementById("posPedidosApedidoBadge");
      const r = resumen || {};
      const total = parseInt(r.total, 10) || 0;
      const vencidos = parseInt(r.vencidos, 10) || 0;
      const listos = parseInt(r.listos, 10) || 0;
      if (badge) {
        badge.textContent = String(total);
        badge.classList.toggle("d-none", total <= 0);
      }
      if (!box) return;
      if (!total) {
        box.innerHTML = '<span class="badge text-bg-secondary">Sin pedidos abiertos</span>';
        return;
      }
      let html =
        '<span class="badge text-bg-primary">' +
        total +
        " abiertos</span>";
      if (listos) html += '<span class="badge text-bg-info">' + listos + " listos retiro</span>";
      if (vencidos) html += '<span class="badge text-bg-danger">' + vencidos + " vencidos</span>";
      box.innerHTML = html;
    }

    function posRenderPedidosApedido(items) {
      if (!items || !items.length) {
        listEl.innerHTML =
          '<p class="text-muted small py-4 mb-0 text-center">No hay pedidos en esta vista.</p>';
        return;
      }
      listEl.innerHTML = items
        .map(function (it) {
          const venc = it.vencido ? " pos-pedido-card--vencido" : "";
          const wa = it.notificar_whatsapp
            ? '<span class="badge text-bg-success"><i class="fab fa-whatsapp me-1"></i>WA</span>'
            : "";
          const tel = it.telefono
            ? '<span class="text-muted font-monospace small">' + escapeHtmlPosJs(it.telefono) + "</span>"
            : '<span class="text-danger small">Sin teléfono</span>';
          let acciones = "";
          if (it.estado === "por_pedir") {
            acciones +=
              '<button type="button" class="btn btn-sm btn-outline-primary pos-pedido-accion" data-accion="listo" data-id="' +
              it.id +
              '">Marcar listo</button>';
          }
          if (it.estado === "listo" || it.estado === "por_pedir") {
            if (it.whatsapp_url) {
              acciones +=
                '<a class="btn btn-sm btn-success" target="_blank" rel="noopener" href="' +
                escapeHtmlPosJs(it.whatsapp_url) +
                '" data-accion="wa" data-id="' +
                it.id +
                '"><i class="fab fa-whatsapp me-1"></i>Avisar</a>';
            }
            acciones +=
              '<button type="button" class="btn btn-sm btn-outline-success pos-pedido-accion" data-accion="entregado" data-id="' +
              it.id +
              '">Entregado</button>';
          }
          if (it.estado === "avisado") {
            acciones +=
              '<button type="button" class="btn btn-sm btn-success pos-pedido-accion" data-accion="entregado" data-id="' +
              it.id +
              '">Entregado</button>';
          }
          const ticket = it.ticket_url
            ? '<a class="btn btn-sm btn-link py-0" href="' +
              escapeHtmlPosJs(it.ticket_url) +
              '" target="_blank" rel="noopener">Vale #' +
              escapeHtmlPosJs(String(it.venta_id)) +
              "</a>"
            : "Vale #" + escapeHtmlPosJs(String(it.venta_id));
          return (
            '<article class="pos-pedido-card' +
            venc +
            '" data-pedido-id="' +
            it.id +
            '">' +
            '<div class="pos-pedido-card__head">' +
            '<span class="badge text-bg-' +
            escapeHtmlPosJs(it.estado_badge || "secondary") +
            '">' +
            escapeHtmlPosJs(it.estado_label || it.estado) +
            "</span>" +
            wa +
            (it.vencido ? '<span class="badge text-bg-danger ms-1">Vencido</span>' : "") +
            "</div>" +
            '<h6 class="pos-pedido-card__title mb-1">' +
            escapeHtmlPosJs(it.producto_nombre) +
            ' <span class="text-muted">×' +
            escapeHtmlPosJs(String(it.cantidad)) +
            "</span></h6>" +
            '<p class="small mb-1"><strong>' +
            escapeHtmlPosJs(it.cliente_nombre) +
            "</strong>" +
            (it.cliente_rut ? " · " + escapeHtmlPosJs(it.cliente_rut) : "") +
            "</p>" +
            '<p class="small text-muted mb-1"><i class="fas fa-calendar-day me-1"></i>' +
            escapeHtmlPosJs(it.fecha_promesa_fmt) +
            " · " +
            escapeHtmlPosJs(it.modalidad_label) +
            "</p>" +
            '<p class="small mb-2 d-flex flex-wrap align-items-center gap-2">' +
            tel +
            " · " +
            ticket +
            " · " +
            escapeHtmlPosJs(it.vale_estado) +
            " " +
            escapeHtmlPosJs(it.vale_total_fmt || "") +
            "</p>" +
            '<div class="pos-pedido-card__actions d-flex flex-wrap gap-1">' +
            acciones +
            "</div></article>"
          );
        })
        .join("");
    }

    async function posCargarPedidosApedido() {
      listEl.innerHTML = '<p class="text-muted small py-3 mb-0">Cargando…</p>';
      const q = filtroActivo === "todos" ? "?estado=todos" : "?estado=abiertos";
      try {
        const res = await fetch(baseUrl + q, {
          credentials: "same-origin",
          headers: { Accept: "application/json" },
        });
        const data = await res.json();
        if (data && data.ok) {
          posRenderPedidosResumen(data.resumen);
          posRenderPedidosApedido(data.items || []);
        } else {
          listEl.innerHTML =
            '<p class="text-danger small py-3 mb-0">No se pudo cargar la bandeja.</p>';
        }
      } catch (_err) {
        listEl.innerHTML =
          '<p class="text-danger small py-3 mb-0">Error de conexión.</p>';
      }
    }

    async function posActualizarEstadoPedido(id, estado, silent) {
      try {
        const res = await fetch(pedidoEstadoUrl(id), {
          method: "POST",
          credentials: "same-origin",
          headers: { "Content-Type": "application/json", Accept: "application/json" },
          body: JSON.stringify({ estado: estado }),
        });
        const data = await res.json();
        if (data && data.ok) {
          if (data.resumen) posRenderPedidosResumen(data.resumen);
          if (!silent) mostrarPosToast(data.mensaje || "Estado actualizado.");
          await posCargarPedidosApedido();
          return true;
        }
        mostrarPosToast((data && data.mensaje) || "No se pudo actualizar.", { variant: "warning" });
      } catch (_err) {
        mostrarPosToast("Error al actualizar pedido.", { variant: "danger" });
      }
      return false;
    }

    document.querySelectorAll(".pos-pedidos-filtro").forEach(function (btn) {
      btn.addEventListener("click", function () {
        filtroActivo = btn.getAttribute("data-pedidos-filtro") || "abiertos";
        document.querySelectorAll(".pos-pedidos-filtro").forEach(function (b) {
          const on = b === btn;
          b.classList.toggle("btn-primary", on);
          b.classList.toggle("btn-outline-secondary", !on);
          b.classList.toggle("active", on);
        });
        posCargarPedidosApedido();
      });
    });

    const btnRef = document.getElementById("posPedidosApedidoRefresh");
    if (btnRef) btnRef.addEventListener("click", posCargarPedidosApedido);

    listEl.addEventListener("click", function (e) {
      const btn = e.target.closest(".pos-pedido-accion");
      if (btn) {
        e.preventDefault();
        const id = btn.getAttribute("data-id");
        const acc = btn.getAttribute("data-accion");
        const map = { listo: "listo", entregado: "entregado" };
        if (id && map[acc]) posActualizarEstadoPedido(id, map[acc]);
        return;
      }
      const wa = e.target.closest("a[data-accion='wa']");
      if (wa) {
        const id = wa.getAttribute("data-id");
        if (id) {
          window.setTimeout(function () {
            posActualizarEstadoPedido(id, "avisado", true);
          }, 600);
        }
      }
    });

    if (panelEl) {
      panelEl.addEventListener("shown.bs.offcanvas", posCargarPedidosApedido);
    }
    posCargarPedidosApedido();
  }

  function posResumeStorageKey(ventaId) {
    return "pos_resume_ack_" + String(ventaId || "");
  }

  /** Modales dentro de .pos-vendedor-page (overflow:hidden) quedan bajo el backdrop; anclar en body. */
  function posAnclarModalEnBody(modalEl) {
    if (!modalEl || modalEl.parentNode === document.body) return;
    document.body.appendChild(modalEl);
  }

  async function posIniciarNuevaVenta(urlNuevaVenta) {
    if (!urlNuevaVenta) {
      mostrarPosToast("Nueva venta no disponible.", { variant: "danger" });
      return false;
    }
    try {
      const res = await fetch(urlNuevaVenta, {
        method: "POST",
        credentials: "same-origin",
        headers: { "Content-Type": "application/json", Accept: "application/json" },
        body: JSON.stringify({ motivo: "POS — nueva venta (borrador descartado)" }),
      });
      const data = await res.json().catch(function () {
        return {};
      });
      if (!res.ok || !data.ok) {
        mostrarPosToast(data.mensaje || "No se pudo iniciar nueva venta.", { variant: "warning" });
        return false;
      }
      if (data.venta_id) {
        try {
          sessionStorage.removeItem(posResumeStorageKey(data.venta_id));
        } catch (_e) {
          /* ignore */
        }
      }
      window.location.reload();
      return true;
    } catch (_e) {
      mostrarPosToast("Error de red al iniciar nueva venta.", { variant: "danger" });
      return false;
    }
  }

  function wirePosValeResumePrompt(cfg) {
    const resume = cfg && cfg.vale_resume;
    if (!resume || !resume.show) return;
    const ventaId = resume.venta_id;
    try {
      if (sessionStorage.getItem(posResumeStorageKey(ventaId)) === "1") return;
    } catch (_e) {
      /* ignore */
    }
    const modalEl = document.getElementById("modalPosValeResume");
    if (!modalEl || typeof bootstrap === "undefined") return;
    const itemsEl = document.getElementById("posValeResumeItems");
    const totalEl = document.getElementById("posValeResumeTotal");
    const idEl = document.getElementById("posValeResumeValeId");
    if (itemsEl) itemsEl.textContent = String(resume.items_count || 0);
    if (totalEl) totalEl.textContent = resume.total_fmt || "$0";
    if (idEl) idEl.textContent = String(ventaId || "—");
    posSearchPanelCerrar();
    posAnclarModalEnBody(modalEl);
    const inst = bootstrap.Modal.getOrCreateInstance(modalEl);
    const urlNueva = cfg.urls && cfg.urls.nueva_venta;

    function posValeResumeContinuar() {
      try {
        sessionStorage.setItem(posResumeStorageKey(ventaId), "1");
      } catch (_e2) {
        /* ignore */
      }
      inst.hide();
      const inp = posInputBusqueda();
      if (inp) inp.focus();
    }

    function posValeResumeNueva(btn) {
      if (!urlNueva) {
        mostrarPosToast("Nueva venta no disponible (falta URL en configuración).", { variant: "danger" });
        return;
      }
      if (btn) btn.disabled = true;
      posIniciarNuevaVenta(urlNueva).finally(function () {
        if (btn) btn.disabled = false;
      });
    }

    if (!modalEl.dataset.posValeResumeWired) {
      modalEl.dataset.posValeResumeWired = "1";
      modalEl.addEventListener("click", function (ev) {
        if (ev.target.closest("#posValeResumeContinue")) {
          ev.preventDefault();
          ev.stopPropagation();
          posValeResumeContinuar();
          return;
        }
        if (ev.target.closest("#posValeResumeNueva")) {
          ev.preventDefault();
          ev.stopPropagation();
          posValeResumeNueva(ev.target.closest("#posValeResumeNueva"));
        }
      });
    }
    const btnContinue = document.getElementById("posValeResumeContinue");
    const btnNueva = document.getElementById("posValeResumeNueva");
    if (btnContinue) {
      btnContinue.type = "button";
      btnContinue.onclick = function (ev) {
        ev.preventDefault();
        posValeResumeContinuar();
      };
    }
    if (btnNueva) {
      btnNueva.type = "button";
      btnNueva.onclick = function (ev) {
        ev.preventDefault();
        posValeResumeNueva(btnNueva);
      };
    }
    inst.show();
  }

  function posRetiroSugeridoDesdeItem(it) {
    if (!it) return "Tienda";
    const st = Number(it.stock_tienda || 0);
    const sb = Number(it.stock_bodega || 0);
    if (st > 0) return "Tienda";
    if (sb > 0) return "Bodega";
    return "Tienda";
  }

  function posAsegurarDockVisible() {
    const dock = document.getElementById("posCheckoutDock");
    if (!dock) return;
    dock.style.removeProperty("display");
    dock.style.removeProperty("visibility");
    dock.style.removeProperty("opacity");
  }

  var posSearchBusyTimer = null;

  function posSearchBusyTimeoutClear() {
    if (posSearchBusyTimer) {
      clearTimeout(posSearchBusyTimer);
      posSearchBusyTimer = null;
    }
  }

  /** Evita panel “Agregando…” pegado si falla red o respuesta. */
  function posSearchBusyArm(panel, ms) {
    posSearchBusyTimeoutClear();
    if (!panel) return;
    panel.classList.add("pos-search-suggestions--busy");
    posSearchBusyTimer = setTimeout(function () {
      panel.classList.remove("pos-search-suggestions--busy");
      posSearchBusyTimer = null;
    }, ms || 14000);
  }

  function posSearchBusyRelease(panel) {
    posSearchBusyTimeoutClear();
    if (panel) panel.classList.remove("pos-search-suggestions--busy");
  }

  function posEsPantallaVendedora() {
    return document.body.classList.contains("pos-pantalla-vendedora");
  }

  var posCartPersistBusy = {};
  var posSearchPanelAnchor = { parent: null, next: null };

  function posMontarPanelBusqueda(panel, anchorInput) {
    if (!panel || !anchorInput || !posEsPantallaVendedora()) return;
    if (!posSearchPanelAnchor.parent) {
      posSearchPanelAnchor.parent = panel.parentNode;
      posSearchPanelAnchor.next = panel.nextSibling;
    }
    if (panel.parentNode !== document.body) {
      document.body.appendChild(panel);
    }
    const relayoutBusqueda = document.body.classList.contains("pos-dock-relayout-busqueda");
    const dock = document.getElementById("posCheckoutDock");
    const dockH = dock ? dock.offsetHeight : 120;
    const inputRect = anchorInput.getBoundingClientRect();
    const hero = anchorInput.closest(".pos-unified-search-hero");
    const toolsCol = document.querySelector(".pos-premium-col--tools");
    const box = toolsCol
      ? toolsCol.getBoundingClientRect()
      : hero
        ? hero.getBoundingClientRect()
        : inputRect;
    const inset = 4;
    const left = Math.max(8, box.left + inset);
    const maxW = Math.min(760, window.innerWidth - left - 12);
    const width = Math.min(maxW, Math.max(520, box.width - inset * 2));
    const maxH = Math.max(160, window.innerHeight - dockH - inputRect.bottom - 16);
    panel.classList.add("pos-search-suggestions--portal");
    if (relayoutBusqueda) {
      panel.classList.add("pos-search-suggestions--portal-alta");
    } else {
      panel.classList.remove("pos-search-suggestions--portal-alta");
    }
    panel.style.position = "fixed";
    panel.style.left = left + "px";
    panel.style.top = inputRect.bottom + 6 + "px";
    panel.style.width = width + "px";
    if (relayoutBusqueda) {
      panel.style.removeProperty("max-height");
      panel.style.removeProperty("height");
    } else {
      panel.style.maxHeight = maxH + "px";
    }
    panel.style.zIndex = relayoutBusqueda ? "1250" : "1200";
    panel.style.boxSizing = "border-box";
  }

  function posDesmontarPanelBusqueda(panel) {
    if (!panel) return;
    panel.classList.remove("pos-search-suggestions--portal");
    panel.classList.remove("pos-search-suggestions--portal-alta");
    panel.removeAttribute("style");
    if (posSearchPanelAnchor.parent && panel.parentNode === document.body) {
      posSearchPanelAnchor.parent.insertBefore(panel, posSearchPanelAnchor.next);
    }
  }

  async function posPersistirLineaAjax(detalleId, urlActualizarItem, opts) {
    opts = opts || {};
    const cantidadEl = document.getElementById("cantidad_" + detalleId);
    const descuentoEl = document.getElementById("descuento_" + detalleId);
    if (!cantidadEl || !descuentoEl || !urlActualizarItem) return false;
    if (posCartPersistBusy[detalleId]) return false;
    posCartPersistBusy[detalleId] = true;
    const fd = new FormData();
    fd.append("actualizar", String(detalleId));
    fd.append("cantidad_" + detalleId, cantidadEl.value);
    fd.append("descuento_" + detalleId, posDescuentoValorParaServidor(detalleId));
    fd.append("pos_ajax", "1");
    if (opts.solo_cantidad) fd.append("solo_cantidad", "1");
    if (opts.supervisor_tarjeta) fd.append("supervisor_tarjeta", opts.supervisor_tarjeta);
    if (opts.supervisor_pin) fd.append("supervisor_pin", opts.supervisor_pin);
    if (opts.supervisor_identificador) {
      fd.append("supervisor_identificador", opts.supervisor_identificador);
    }
    if (opts.supervisor_clave) fd.append("supervisor_clave", opts.supervisor_clave);
    const cfgDeck = readPosConfig();
    if (cfgDeck && cfgDeck.from_command_deck) fd.append("from_command_deck", "1");
    try {
      const res = await fetch(urlActualizarItem, {
        method: "POST",
        credentials: "same-origin",
        body: fd,
        headers: { Accept: "application/json" },
      });
      const data = await res.json().catch(function () {
        return {};
      });
      if (!res.ok || !data.ok) {
        mostrarPosToast(data.mensaje || "No se pudo guardar la línea.");
        if (descuentoEl) {
          descuentoEl.value = descuentoEl.dataset.descuentoServidor || "0";
          posSyncDtoChip(detalleId);
          const precio = parseFloat(descuentoEl.dataset.precio || cantidadEl.dataset.precio || "0") || 0;
          actualizarSubtotal(detalleId, precio);
        }
        return false;
      }
      if (descuentoEl) {
        descuentoEl.dataset.descuentoServidor = String(descuentoEl.value || "0");
      }
      if (typeof data.venta_total === "number") actualizarTotalesVisuales(data.venta_total);
      const dockCount = document.getElementById("posDockItemCount");
      if (dockCount && typeof data.items_count === "number") {
        dockCount.textContent = String(data.items_count);
      }
      actualizarEstadoEmisionVale();
      if (opts.refrescar_carrito) {
        await posRefrescarCarritoVendedor();
        if (cfgDeck && cfgDeck.urls) posBindCartLineHandlers(cfgDeck.urls, !!cfgDeck.descuento_libre);
        posCerrarTodosMenusDto();
      }
      return true;
    } catch (_e) {
      mostrarPosToast("Error de red al guardar la línea.");
      return false;
    } finally {
      delete posCartPersistBusy[detalleId];
    }
  }

  async function posEliminarLineaCarrito(form) {
    if (!form || !form.action) return false;
    if (!confirm("¿Eliminar este producto de la venta?")) return false;
    const fd = new FormData();
    fd.append("pos_ajax", "1");
    try {
      const res = await fetch(form.action, {
        method: "POST",
        credentials: "same-origin",
        body: fd,
        headers: { Accept: "application/json" },
      });
      const data = await res.json().catch(function () {
        return {};
      });
      if (!res.ok || !data.ok) {
        mostrarPosToast("No se pudo eliminar la línea.");
        return false;
      }
      if (typeof data.venta_total === "number") actualizarTotalesVisuales(data.venta_total);
      await posRefrescarCarritoVendedor();
      actualizarEstadoEmisionVale();
      posAsegurarDockVisible();
      return true;
    } catch (_e) {
      mostrarPosToast("Error de red al eliminar.");
      return false;
    }
  }

  function posUrlRetiroLinea(cfg) {
    cfg = cfg || readPosConfig();
    if (!cfg || !cfg.urls) return "";
    return cfg.urls.retiro_linea || cfg.urls.actualizar_item || "";
  }

  function posSyncRetiroSelectsPrev() {
    document.querySelectorAll(".pos-retiro-select").forEach(function (sel) {
      if (!sel.getAttribute("data-retiro-prev")) {
        sel.setAttribute("data-retiro-prev", sel.value);
      }
    });
  }

  function posBindRetiroLineaHandlers() {
    const cfg = readPosConfig();
    if (!cfg || !cfg.pos_retiro_por_linea || !posEsPantallaVendedora()) return;
    if (!posUrlRetiroLinea(cfg)) return;
    posSyncRetiroSelectsPrev();
    if (window._posRetiroLineaDelegado) return;
    window._posRetiroLineaDelegado = true;
    document.addEventListener(
      "mousedown",
      function (e) {
        if (e.target && e.target.closest && e.target.closest(".pos-retiro-select")) {
          e.stopPropagation();
        }
      },
      true
    );
    document.addEventListener("change", function (e) {
      const sel = e.target;
      if (!sel || !sel.classList || !sel.classList.contains("pos-retiro-select")) return;
      if (!posEsPantallaVendedora() || sel.disabled) return;
      const detalleId = parseInt(sel.getAttribute("data-detalle-id"), 10);
      if (isNaN(detalleId)) return;
      const nuevo = (sel.value || "Tienda").trim();
      const prev = (sel.getAttribute("data-retiro-prev") || "").trim();
      if (nuevo === prev) return;
      const url = posUrlRetiroLinea();
      if (!url) return;
      posActualizarRetiroLinea(detalleId, nuevo, url).then(function (ok) {
        if (ok) {
          sel.setAttribute("data-retiro-prev", nuevo);
          mostrarPosToast("Retiro: " + nuevo, { delay: 1200 });
          validarStockLinea(detalleId);
          actualizarEstadoEmisionVale();
        }
      });
    });
  }

  function posBindDtoQuickButtons(u, descLibre) {
    const list = document.getElementById("contenedor-carrito");
    if (!list || !u || !u.actualizar_item) return;
    $(list).off("click.posdtoquick", ".pos-dto-quick__btn");
    $(list).on("click.posdtoquick", ".pos-dto-quick__btn", function (e) {
      e.preventDefault();
      e.stopPropagation();
      const det = this.closest(".pos-cart-card__more");
      const inp = det && det.querySelector(".descuento-input");
      if (!inp) return;
      const detalleId = inp.getAttribute("data-detalle-id");
      const pct = this.getAttribute("data-pct");
      if (!detalleId || pct == null) return;
      posAplicarDescuentoRapido(detalleId, pct, !!descLibre, u.actualizar_item);
    });
  }

  function posBindCartLineHandlers(u, descLibre) {
    if (!u || !u.actualizar_item) return;
    posBindDtoQuickButtons(u, descLibre);
    $(".cantidad-input").off(".posbind");
    $(".cantidad-input").on("input.posbind change.posbind", function () {
      const detalleId = $(this).data("detalle-id");
      const precio = parseFloat($(this).data("precio")) || 0;
      actualizarSubtotal(detalleId, precio);
      actualizarEstadoEmisionVale();
      schedulePersistDetalle(detalleId, u.actualizar_item, true);
    });
    $(".descuento-input").off(".posbind");
    $(".descuento-input").on("focus.posbind", function () {
      try {
        this.select();
      } catch (_e) {
        /* ignore */
      }
    });
    $(".descuento-input").on("input.posbind", function () {
      const detalleId = $(this).data("detalle-id");
      const precio = parseFloat($(this).data("precio")) || 0;
      actualizarSubtotal(detalleId, precio);
      actualizarEstadoEmisionVale();
      posSyncDtoChip(detalleId);
      posAbrirMenuDtoSiCorresponde(detalleId);
    });
    $(".descuento-input").on("keydown.posbind", function (e) {
      if (e.key !== "Enter") return;
      e.preventDefault();
      const detalleId = $(this).data("detalle-id");
      cancelPersistDetalle(detalleId);
      posIntentarGuardarLineaConAutorizacionDesc(detalleId, descLibre, u.actualizar_item, {
        cerrar_menu: true,
      });
    });
    $(".descuento-input").on("change.posbind", function () {
      const detalleId = $(this).data("detalle-id");
      cancelPersistDetalle(detalleId);
      posIntentarGuardarLineaConAutorizacionDesc(detalleId, descLibre, u.actualizar_item, {});
    });
    $(".btn-ajustar-cantidad").off("click.posbind");
    $(".btn-ajustar-cantidad").on("click.posbind", function () {
      const detalleId = parseInt($(this).data("detalle-id"), 10);
      const delta = parseInt($(this).data("delta"), 10);
      const precio = parseFloat($(this).data("precio")) || 0;
      ajustarCantidad(detalleId, delta, precio);
      actualizarEstadoEmisionVale();
      schedulePersistDetalle(detalleId, u.actualizar_item, true);
    });
    posBindRetiroLineaHandlers();
    $(".btn-actualizar-item").off("click.posbind");
    $(".btn-actualizar-item").on("click.posbind", function () {
      const detalleId = parseInt($(this).data("detalle-id"), 10);
      cancelPersistDetalle(detalleId);
      posIntentarGuardarLineaConAutorizacionDesc(detalleId, descLibre, u.actualizar_item, {});
    });
  }

  function posSearchPanelLiberar() {
    posSearchBusyTimeoutClear();
    const panel = document.getElementById("pos-search-suggestions");
    if (panel) {
      panel.classList.remove("pos-search-suggestions--busy");
    }
    const hero = document.querySelector(".pos-unified-search-hero, .pos-manual-search-hero");
    if (hero) {
      hero.classList.remove("pos-unified-search-hero--suggest-open");
      hero.classList.remove("pos-manual-search-hero--suggest-open");
    }
  }

  function posSearchPanelCerrar() {
    const panel = document.getElementById("pos-search-suggestions");
    if (!panel) return;
    panel.classList.remove("pos-search-suggestions--busy");
    panel.classList.add("d-none");
    panel.innerHTML = "";
    const hero = document.querySelector(".pos-unified-search-hero, .pos-manual-search-hero");
    if (hero) {
      hero.classList.remove("pos-unified-search-hero--suggest-open");
      hero.classList.remove("pos-manual-search-hero--suggest-open");
    }
    const banner = document.getElementById("posBannerApedido");
    if (banner) banner.classList.add("d-none");
    if (typeof window.posSyncHudSearchFocus === "function") {
      window.posSyncHudSearchFocus();
    }
  }

  async function posActualizarRetiroLinea(detalleId, valor, urlRetiro) {
    if (!detalleId || !urlRetiro) return false;
    const sel = document.querySelector(
      '.pos-retiro-select[data-detalle-id="' + detalleId + '"]'
    );
    const valorAnterior = sel ? sel.getAttribute("data-retiro-prev") || sel.value : null;
    const usaApiJson = urlRetiro.indexOf("/api/pos/retiro-linea") >= 0;
    if (sel) {
      sel.classList.add("pos-retiro-select--saving");
      sel.setAttribute("aria-busy", "true");
    }
    try {
      let res;
      if (usaApiJson) {
        res = await fetch(urlRetiro, {
          method: "POST",
          credentials: "same-origin",
          headers: { "Content-Type": "application/json", Accept: "application/json" },
          body: JSON.stringify({
            detalle_id: detalleId,
            punto_retiro_linea: valor || "Tienda",
          }),
        });
      } else {
        const fd = new FormData();
        fd.append("actualizar", String(detalleId));
        fd.append("solo_retiro_linea", "1");
        fd.append("punto_retiro_linea", valor || "Tienda");
        fd.append("pos_ajax", "1");
        res = await fetch(urlRetiro, {
          method: "POST",
          credentials: "same-origin",
          body: fd,
          headers: { Accept: "application/json" },
        });
      }
      const data = await res.json().catch(function () {
        return {};
      });
      if (!res.ok || !data.ok) {
        if (sel && valorAnterior != null) sel.value = valorAnterior;
        mostrarPosToast(data.mensaje || "No se pudo actualizar el punto de retiro.");
        return false;
      }
      if (sel) sel.setAttribute("data-retiro-prev", sel.value);
      if (sel) {
        const card = sel.closest(".pos-cart-card");
        const chip = card && card.querySelector(".pos-cart-card__chip--retiro");
        if (chip) chip.textContent = sel.value;
      }
      if (typeof data.venta_total === "number") actualizarTotalesVisuales(data.venta_total);
      const dockCount = document.getElementById("posDockItemCount");
      if (dockCount && typeof data.items_count === "number") {
        dockCount.textContent = String(data.items_count);
      }
      return true;
    } catch (_e) {
      if (sel && valorAnterior != null) sel.value = valorAnterior;
      mostrarPosToast("Error de red al actualizar retiro.");
      return false;
    } finally {
      if (sel) {
        sel.classList.remove("pos-retiro-select--saving");
        sel.removeAttribute("aria-busy");
      }
    }
  }

  async function posRefrescarCarritoVendedor() {
    const cfg = readPosConfig();
    const url = cfg && cfg.urls && cfg.urls.carrito_html;
    if (!url || !document.body.classList.contains("pos-pantalla-vendedora")) return false;
    try {
      const res = await fetch(url, {
        method: "GET",
        credentials: "same-origin",
        headers: { Accept: "application/json" },
      });
      const data = await res.json().catch(function () { return {}; });
      if (!res.ok || !data.ok) return false;
      const host = document.getElementById("posCartHost");
      if (host && data.html) host.innerHTML = data.html;
      document.querySelectorAll("[id^='precio_unitario_']").forEach(function (cell) {
        const valor = posReadClpFromEl(cell);
        const suf = (cell.textContent || "").indexOf("c/u") >= 0 ? " c/u" : "";
        posWriteClpToEl(cell, valor, suf);
      });
      document.querySelectorAll("[id^='subtotal_']").forEach(function (cell) {
        posWriteClpToEl(cell, posReadClpFromEl(cell));
      });
      if (typeof data.venta_total === "number") actualizarTotalesVisuales(data.venta_total);
      else actualizarTotalesVisuales(posSumarSubtotalesFilasBrutas());
      const dockCount = document.getElementById("posDockItemCount");
      if (dockCount && typeof data.items_count === "number") {
        dockCount.textContent = String(data.items_count);
      }
      const list = document.getElementById("contenedor-carrito");
      if (list) list.dataset.posCartV2Wired = "";
      wirePosCartV2();
      if (cfg.urls) posBindCartLineHandlers(cfg.urls, !!cfg.descuento_libre);
      posBindRetiroLineaHandlers();
      document.dispatchEvent(new CustomEvent("pos-cart-refreshed"));
      actualizarEstadoEmisionVale();
      posAsegurarDockVisible();
      return true;
    } catch (_e) {
      return false;
    }
  }

  /** Carrito v3 vendedor: foco de línea, menú ⋯, dto colapsado, scroll suave. */
  function wirePosCartV2() {
    const list = document.getElementById("contenedor-carrito");
    if (!list || !document.body.classList.contains("pos-pantalla-vendedora")) return;
    if (list.dataset.posCartV2Wired === "1") return;
    list.dataset.posCartV2Wired = "1";

    list.addEventListener("click", function (e) {
      if (window.ChilematFicha && ChilematFicha.isFichaTrigger && ChilematFicha.isFichaTrigger(e.target)) {
        return;
      }
      if (
        e.target.closest(
          ".pos-retiro-select, .pos-qty-capsule, .pos-cart-card__toolbar, .pos-cart-card__more, .pos-cart-card__delete-btn, button, input, select, label, a"
        )
      ) {
        return;
      }
      const card = e.target.closest(".pos-cart-card");
      if (!card || !list.contains(card)) return;
      list.querySelectorAll(".pos-cart-card--active").forEach(function (c) {
        if (c !== card) c.classList.remove("pos-cart-card--active");
      });
      card.classList.add("pos-cart-card--active");
      try {
        card.scrollIntoView({ block: "nearest", behavior: "smooth" });
      } catch (_e) {
        card.scrollIntoView(false);
      }
    });

    if (!list.dataset.posCartDtoToggleWired) {
      list.dataset.posCartDtoToggleWired = "1";
      list.addEventListener(
        "toggle",
        function (e) {
          const det = e.target;
          if (!det || !det.classList || !det.classList.contains("pos-cart-card__more")) return;
          list.querySelectorAll(".pos-cart-card--dto-open").forEach(function (c) {
            c.classList.remove("pos-cart-card--dto-open");
          });
          const card = det.closest(".pos-cart-card");
          if (!det.open) return;
          if (card) card.classList.add("pos-cart-card--dto-open");
          list.querySelectorAll(".pos-cart-card__more[open]").forEach(function (other) {
            if (other !== det) other.open = false;
          });
          const inp = det.querySelector(".descuento-input");
          const detId = inp && inp.getAttribute("data-detalle-id");
          if (detId) posFocusDescuentoInput(detId);
        },
        true
      );
    }

    if (!list.dataset.posDtoPanelShieldWired) {
      list.dataset.posDtoPanelShieldWired = "1";
      list.addEventListener(
        "click",
        function (e) {
          if (!e.target.closest(".pos-cart-card__more-panel")) return;
          if (
            e.target.closest(
              ".pos-dto-quick__btn, .descuento-input, .btn-actualizar-item, label, button, input"
            )
          ) {
            return;
          }
          e.stopPropagation();
        },
        true
      );
    }

    list.querySelectorAll(".descuento-input").forEach(function (inp) {
      const detId = inp.getAttribute("data-detalle-id");
      if (detId) posSyncDtoChip(detId);
    });
  }

  function posAbrirMenuDtoSiCorresponde(detalleId) {
    const inp = document.getElementById("descuento_" + detalleId);
    const row = document.getElementById("pos_row_" + detalleId);
    if (!inp || !row) return;
    posSyncDtoChip(detalleId);
    const v = parseFloat(inp.value) || 0;
    if (v <= 0) return;
    const det = row.querySelector(".pos-cart-card__more");
    if (det) det.open = true;
  }

  /**
   * Asistente de búsqueda manual: input único + panel de tarjetas (sin Select2 visible).
   */
  function initPosManualSearch(buscarUrl) {
    const panel = document.getElementById("pos-search-suggestions");
    const input = posInputBusqueda();
    const hero = document.querySelector(".pos-unified-search-hero, .pos-manual-search-hero");
    if (!panel || !input || !buscarUrl) return null;

    function setSuggestOpen(open) {
      if (!hero) return;
      hero.classList.toggle("pos-manual-search-hero--suggest-open", !!open);
      hero.classList.toggle("pos-unified-search-hero--suggest-open", !!open);
      if (typeof window.posSyncHudSearchFocus === "function") {
        window.posSyncHudSearchFocus();
      }
    }

    let activeIndex = -1;
    let lastItems = [];
    let debounceTimer = null;
    let fetchCtrl = null;
    let pendingApedidoIdx = null;
    const bannerApedido = document.getElementById("posBannerApedido");

    function hidePanel() {
      panel.classList.add("d-none");
      panel.innerHTML = "";
      posDesmontarPanelBusqueda(panel);
      activeIndex = -1;
      lastItems = [];
      pendingApedidoIdx = null;
      if (bannerApedido) bannerApedido.classList.add("d-none");
      setSuggestOpen(false);
    }

    function syncPanelBusquedaVisible() {
      if (panel.classList.contains("d-none")) return;
      posMontarPanelBusqueda(panel, input);
    }

    function esSemaforoAzul(it) {
      return it && String(it.semaforo || "").toLowerCase() === "azul";
    }

    /** Venta en verde: semáforo azul o sin stock en tienda/bodega con flag habilitado. */
    function debeAgregarComoApedido(it) {
      if (!it || it.permite_venta_verde === false) return false;
      if (esSemaforoAzul(it)) return true;
      return itemSinStock(it);
    }

    function requiereConfirmacionApedido(it) {
      return debeAgregarComoApedido(it);
    }

    function avisoToastApedido(it) {
      const dias = Number((it && it.dias_entrega_estimado) || 5);
      mostrarPosToast(
        "Producto a pedido. Confirme tiempo estimado con el cliente (~" + dias + " días hábiles).",
        { delay: 3200, variant: "info" }
      );
    }

    function mostrarBannerApedido(it) {
      if (!bannerApedido || !it) return;
      const dias = Number(it.dias_entrega_estimado || 5);
      bannerApedido.innerHTML =
        '<div class="pos-banner-apedido__inner">' +
        '<strong>Paso 2 — Agregar a pedido</strong> — Entrega estimada: ' +
        dias +
        " días hábiles. Confirme con el cliente y pulse " +
        '<button type="button" class="btn btn-sm btn-primary ms-1" id="posBtnConfirmarApedido">Confirmar y agregar</button>' +
        '<button type="button" class="btn btn-sm btn-link" id="posBtnCancelarApedido">Cancelar</button>' +
        " (o Enter / segundo clic en la tarjeta)." +
        "</div>";
      bannerApedido.classList.remove("d-none");
      panel.querySelectorAll(".pos-search-card").forEach(function (el, i) {
        el.classList.toggle("pos-search-card--apedido-pendiente", pendingApedidoIdx === i);
      });
      const btnOk = document.getElementById("posBtnConfirmarApedido");
      const btnNo = document.getElementById("posBtnCancelarApedido");
      if (btnOk) {
        btnOk.addEventListener("click", function (ev) {
          ev.preventDefault();
          ev.stopPropagation();
          if (pendingApedidoIdx !== null) seleccionarItem(pendingApedidoIdx, true);
        });
        try {
          btnOk.focus({ preventScroll: true });
        } catch (_e) {
          btnOk.focus();
        }
      }
      if (btnNo) {
        btnNo.addEventListener("click", function (ev) {
          ev.preventDefault();
          ev.stopPropagation();
          pendingApedidoIdx = null;
          bannerApedido.classList.add("d-none");
          panel.querySelectorAll(".pos-search-card").forEach(function (el) {
            el.classList.remove("pos-search-card--apedido-pendiente");
          });
        });
      }
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
      if (
        t === "economica" ||
        t === "premium" ||
        t === "verde" ||
        t === "amarillo" ||
        t === "azul" ||
        t === "tienda" ||
        t === "bodega" ||
        t === "sin_stock"
      ) {
        return "pos-search-badge pos-search-badge--" + t;
      }
      return "pos-search-badge";
    }

    function semaforoCardClass(it) {
      const s = String((it && it.semaforo) || "").toLowerCase();
      if (s === "verde" || s === "amarillo" || s === "azul") {
        return " pos-search-card--semaforo-" + s;
      }
      return "";
    }

    function semaforoLuzHtml(it) {
      const s = String((it && it.semaforo) || "verde").toLowerCase();
      const txt =
        s === "amarillo"
          ? "Bodega"
          : s === "azul"
            ? "A pedido"
            : "Tienda";
      const label = escapeHtml(it.semaforo_label || txt);
      return (
        '<div class="pos-semaforo-luz pos-semaforo-luz--' +
        s +
        '" title="' +
        label +
        '">' +
        '<span class="pos-semaforo-luz__dot" aria-hidden="true"></span>' +
        '<span class="pos-semaforo-luz__txt">' +
        escapeHtml(txt) +
        "</span></div>"
      );
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

    function itemSinStock(it) {
      if (it && String(it.semaforo || "").toLowerCase() === "azul") return true;
      if (it && it.sin_stock === true) return true;
      const st = Number(it.stock_tienda || 0);
      const sb = Number(it.stock_bodega || 0);
      const tot = Number(it.stock_total != null ? it.stock_total : st + sb);
      return tot <= 0;
    }

    function precioFmtLista(it) {
      const p = Number(it.precio);
      if (!isNaN(p) && p > 0) return formatoCLP(Math.round(p));
      if (it.precio_fmt) return String(it.precio_fmt);
      return formatoCLP(0);
    }

    function indicePrimeroConStock(items) {
      for (let i = 0; i < items.length; i++) {
        const s = String(items[i].semaforo || "").toLowerCase();
        if (s === "verde" || s === "amarillo") return i;
      }
      for (let j = 0; j < items.length; j++) {
        if (!esSemaforoAzul(items[j])) return j;
      }
      return items.length ? 0 : -1;
    }

    function stockLinea(it) {
      const u = escapeHtml(it.unidad || "un");
      const st = Number(it.stock_tienda || 0);
      const sb = Number(it.stock_bodega || 0);
      const tot = Number(it.stock_total != null ? it.stock_total : st + sb);
      const agotado = itemSinStock(it);
      const cls = agotado ? " pos-search-card__stock--agotado" : "";
      if (st > 0 && sb > 0) {
        return (
          '<span class="' +
          cls.trim() +
          '">Stock: <strong>' +
          tot +
          " " +
          u +
          "</strong> (Tienda: " +
          st +
          " / Bodega: " +
          sb +
          ")</span>"
        );
      }
      if (st > 0) {
        return (
          '<span class="' +
          cls.trim() +
          '">Stock: <strong>' +
          st +
          " " +
          u +
          "</strong> (Tienda)</span>"
        );
      }
      if (sb > 0) {
        return (
          '<span class="' +
          cls.trim() +
          '">Stock: <strong>' +
          sb +
          " " +
          u +
          "</strong> (Bodega)</span>"
        );
      }
      return (
        '<span class="pos-search-card__stock--agotado">Sin stock en tienda ni bodega · <strong>0</strong> ' +
        u +
        "</span>"
      );
    }

    function renderItems(items, searchMeta) {
      if (!items.length) {
        const emptyBody = searchMeta
          ? mensajeSinCoincidencias(searchMeta)
          : "Sin coincidencias. Pruebe otro término o use <strong>Catálogo</strong>.";
        panel.innerHTML =
          '<div class="pos-search-suggestions__head">Asistente de precios</div>' +
          '<div class="pos-search-suggestions__empty">' +
          emptyBody +
          "</div>";
        panel.classList.remove("d-none");
        setSuggestOpen(true);
        syncPanelBusquedaVisible();
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
          const sinStock = itemSinStock(it);
          return (
            '<article class="pos-search-card pos-search-card--premium' +
            semaforoCardClass(it) +
            (sinStock ? " pos-search-card--sin-stock" : "") +
            (idx === activeIndex ? " is-active" : "") +
            '" role="option" data-idx="' +
            idx +
            '" data-producto-id="' +
            escapeHtml(it.producto_id) +
            '" aria-selected="' +
            (idx === activeIndex ? "true" : "false") +
            '">' +
            semaforoLuzHtml(it) +
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
            escapeHtml(precioFmtLista(it)) +
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
        leyendaSemaforoHtml() +
        html;
      panel.classList.remove("d-none");
      setSuggestOpen(true);
      syncPanelBusquedaVisible();
      panel.querySelectorAll(".pos-search-card").forEach(function (card) {
        card.addEventListener("mousedown", function (e) {
          e.preventDefault();
          const idx = parseInt(card.getAttribute("data-idx"), 10);
          if (isNaN(idx)) return;
          if (pendingApedidoIdx === idx) {
            seleccionarItem(idx, true);
          } else {
            seleccionarItem(idx, false);
          }
        });
      });
    }

    function marcarActivo() {
      panel.querySelectorAll(".pos-search-card").forEach(function (el, i) {
        el.classList.toggle("is-active", i === activeIndex);
        el.setAttribute("aria-selected", i === activeIndex ? "true" : "false");
      });
      const active = panel.querySelector(".pos-search-card.is-active");
      if (active) posPanelScrollToCard(panel, active);
    }

    function setPanelBusy(busy) {
      if (busy) posSearchBusyArm(panel, 14000);
      else posSearchBusyRelease(panel);
    }

    function seleccionarItem(idx, confirmadoApedido) {
      const it = lastItems[idx];
      if (!it || it.producto_id == null) return;
      if (requiereConfirmacionApedido(it) && !confirmadoApedido) {
        pendingApedidoIdx = idx;
        activeIndex = idx;
        marcarActivo();
        avisoToastApedido(it);
        mostrarBannerApedido(it);
        return;
      }
      pendingApedidoIdx = null;
      if (bannerApedido) bannerApedido.classList.add("d-none");
      input.value = "";
      const opts = { punto_retiro_linea: posRetiroSugeridoDesdeItem(it) };
      if (confirmadoApedido && debeAgregarComoApedido(it)) opts.a_pedido = true;
      setPanelBusy(true);
      posEscanearYAgregar(String(it.producto_id), true, opts, panel, setPanelBusy);
    }

    function mensajeSinCoincidencias(data) {
      const filtro = posFiltroBusquedaActual();
      const filtroLabel =
        filtro === "tienda" ? "Solo tienda" : filtro === "catalogo" ? "Catálogo" : "Operativo";
      let msg =
        "Sin coincidencias en modo <strong>" +
        escapeHtml(filtroLabel) +
        "</strong>. Pruebe otro término";
      if (filtro !== "catalogo") {
        msg += ' o pulse <strong>Catálogo</strong>';
      }
      msg += ".";
      if (data && data.meta && data.meta.filtrados_por_stock) {
        msg +=
          " Hay productos en catálogo sin stock en mostrador; use <strong>Catálogo</strong> o <strong>Operativo</strong> (a pedido).";
      }
      return msg;
    }

    function parseBuscarProductoResponse(r) {
      const ct = (r.headers.get("content-type") || "").toLowerCase();
      if (r.status === 401 || r.status === 403) {
        throw new Error("sesion");
      }
      if (r.redirected || (r.url && /\/login/i.test(r.url))) {
        throw new Error("sesion");
      }
      if (!r.ok) {
        throw new Error("http_" + r.status);
      }
      return r.json().catch(function () {
        throw new Error("formato");
      });
    }

    function ejecutarBusqueda(term) {
      const q = (term || "").trim();
      if (q.length < 2) {
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
      syncPanelBusquedaVisible();

      const params = new URLSearchParams({
        q: q,
        origen: "pos",
        enriquecido: "1",
        filtro_pos: posFiltroBusquedaActual(),
      });
      fetch(buscarUrl + "?" + params.toString(), {
        credentials: "same-origin",
        headers: { Accept: "application/json", "X-Requested-With": "XMLHttpRequest" },
        signal: fetchCtrl.signal,
      })
        .then(parseBuscarProductoResponse)
        .then(function (data) {
          lastItems = data && Array.isArray(data.results) ? data.results : [];
          activeIndex = indicePrimeroConStock(lastItems);
          if (lastItems.length) {
            renderItems(lastItems);
          } else {
            renderItems([], data);
          }
        })
        .catch(function (err) {
          if (err && err.name === "AbortError") return;
          let msg = "No se pudo cargar la búsqueda. Revise conexión e intente de nuevo.";
          if (err && err.message === "sesion") {
            msg = "Sesión expirada. Recargue la página (F5) e ingrese de nuevo.";
          } else if (err && String(err.message || "").indexOf("http_") === 0) {
            msg = "Error del servidor (" + String(err.message).replace("http_", "") + ").";
          } else if (err && err.message === "formato") {
            msg = "Respuesta inválida (¿sesión cerrada?). Recargue la página.";
          }
          panel.innerHTML =
            '<div class="pos-search-suggestions__head">Asistente de precios</div>' +
            '<div class="pos-search-suggestions__empty">' +
            escapeHtml(msg) +
            "</div>";
          panel.classList.remove("d-none");
          setSuggestOpen(true);
          syncPanelBusquedaVisible();
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
          if (posEsBusquedaUnificada() && posPareceCodigoBarras(q)) {
            e.preventDefault();
            input.value = "";
            hidePanel();
            posEscanearYAgregar(q, false);
            return;
          }
          if (q.length >= 2) {
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
      } else if (e.key === "Enter") {
        e.preventDefault();
        e.stopPropagation();
        if (pendingApedidoIdx !== null) {
          seleccionarItem(pendingApedidoIdx, true);
        } else if (activeIndex >= 0) {
          seleccionarItem(activeIndex, false);
        }
      }
    }


    input.addEventListener("input", function () {
      clearTimeout(debounceTimer);
      const term = (input.value || "").trim();
      if (term.length < 2) {
        hidePanel();
        return;
      }
      debounceTimer = setTimeout(function () {
        ejecutarBusqueda(term);
      }, 280);
    });

    input.addEventListener("focus", function () {
      const term = (input.value || "").trim();
      if (term.length >= 2 && !lastItems.length) {
        ejecutarBusqueda(term);
      }
    });

    input.addEventListener("keydown", onInputKeydown);

    document.addEventListener("click", function (e) {
      if (!hero) return;
      if (hero.contains(e.target)) return;
      if (panel && panel.contains(e.target)) return;
      hidePanel();
    });

    function agregarDesdeBusquedaManual() {
      if (pendingApedidoIdx !== null) {
        seleccionarItem(pendingApedidoIdx, true);
        return;
      }
      if (lastItems.length && activeIndex >= 0) {
        seleccionarItem(activeIndex, false);
        return;
      }
      const q = (input.value || "").trim();
      if (q.length >= 2) {
        ejecutarBusqueda(q);
        mostrarPosToast("Elija un producto de la lista (flechas y Enter).");
      } else {
        mostrarPosToast("Escriba al menos 2 caracteres para buscar.");
      }
    }

    const formBusqueda = document.getElementById("formAgregarProductoBusqueda");
    if (formBusqueda) {
      formBusqueda.addEventListener("submit", function (e) {
        const hidPid = document.getElementById("posSeleccionProductoId");
        if (hidPid && hidPid.value) return;
        e.preventDefault();
        agregarDesdeBusquedaManual();
      });
    }

    const btnAgregarManual = document.getElementById("posBtnAgregarManual");
    if (btnAgregarManual) {
      btnAgregarManual.addEventListener("click", function (e) {
        e.preventDefault();
        agregarDesdeBusquedaManual();
      });
    }

    window.addEventListener("resize", syncPanelBusquedaVisible);
    window.addEventListener("scroll", syncPanelBusquedaVisible, true);

    return {
      hidePanel: hidePanel,
      focusInput: function () {
        input.focus();
        input.select();
      },
      syncPanel: syncPanelBusquedaVisible,
    };
  }

  function posTotalEfectivoDesdeDom(serverTotal) {
    const sumLineas = posSumarSubtotalesFilasBrutas();
    let srv = 0;
    if (typeof serverTotal === "number" && !isNaN(serverTotal)) {
      srv = Math.max(0, Math.round(serverTotal));
    }
    return Math.max(srv, sumLineas);
  }

  function actualizarTotalesVisuales(total) {
    const rounded = posTotalEfectivoDesdeDom(
      typeof total === "number" ? total : posLeerTotalClpDesdeMontoEl()
    );
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
      dockCount.textContent = String(posContarLineasValeDom());
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
      s += posReadClpFromEl(cell);
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

  async function posEscanearYAgregar(codigo, porProductoId, opts, panelBusyEl, setPanelBusyFn) {
    const cfg = readPosConfig();
    const url = cfg && cfg.urls && cfg.urls.escanear_agregar;
    if (!url) return;
    const payload = porProductoId ? { producto_id: codigo } : { codigo: codigo };
    if (opts && opts.a_pedido) payload.a_pedido = true;
    if (opts && opts.punto_retiro_linea) payload.punto_retiro_linea = opts.punto_retiro_linea;
    function clearBusy() {
      if (typeof setPanelBusyFn === "function") setPanelBusyFn(false);
      else posSearchBusyRelease(panelBusyEl);
    }
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
        const esApedido = !!(opts && opts.a_pedido) || !!data.a_pedido;
        let msg;
        if (esApedido) {
          msg = data.linea_incrementada
            ? "A pedido · cant. " + (data.cantidad_en_vale || "") + ": " + nom
            : "A pedido agregado: " + nom;
        } else {
          msg = data.linea_incrementada
            ? "Cantidad " + (data.cantidad_en_vale || "") + ": " + nom
            : "Agregado: " + nom;
        }
        mostrarPosToast(msg, { delay: esApedido ? 2800 : 1500 });
        if (document.body.classList.contains("pos-pantalla-vendedora")) {
          clearBusy();
          posSearchPanelCerrar();
          const okCart = await posRefrescarCarritoVendedor();
          if (!okCart) window.location.reload();
          const inp = posInputBusqueda();
          if (inp) {
            try {
              inp.focus({ preventScroll: true });
            } catch (_f) {
              inp.focus();
            }
          }
          return;
        }
        posScrollGuardar();
        window.location.reload();
        return;
      }
      clearBusy();
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
      clearBusy();
      mostrarPosToast("Error de red al escanear.");
    } finally {
      clearBusy();
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
        if (document.body.classList.contains("pos-pantalla-vendedora")) {
          posSearchPanelLiberar();
          posSearchPanelCerrar();
          const okCart = await posRefrescarCarritoVendedor();
          if (!okCart) window.location.reload();
          return;
        }
        posScrollGuardar();
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
    const descuento = posDescuentoPctDesdeInput(detalleId);
    const factorStock = parseFloat(document.getElementById("cantidad_" + detalleId).dataset.factorStock || "1") || 1;
    const subtotal = cantidad * precioUnitario * (1 - descuento / 100);
    posWriteClpToEl(document.getElementById("subtotal_" + detalleId), subtotal);
    const consumoEl = document.getElementById("consumo_stock_" + detalleId);
    if (consumoEl) {
      consumoEl.innerText = Math.max(0, Math.round(cantidad * factorStock));
    }

    let total = 0;
    document.querySelectorAll("[id^='subtotal_']").forEach(function (cell) {
      total += posReadClpFromEl(cell);
    });
    actualizarTotalesVisuales(total);
    const precioEl = document.getElementById("precio_unitario_" + detalleId);
    if (precioEl) {
      const suf = document.body.classList.contains("pos-pantalla-vendedora") ? " c/u" : "";
      posWriteClpToEl(precioEl, precioUnitario, suf);
    }
  }

  function posRetiroLineaDetalle(detalleId) {
    const sel = document.getElementById("retiro_" + detalleId);
    if (sel) return (sel.value || "Tienda").trim();
    return "Tienda";
  }

  function posLimiteStockLinea(detalleId) {
    const cantidadEl = document.getElementById("cantidad_" + detalleId);
    if (!cantidadEl) return { limite: 0, etiqueta: "Excede stock en tienda" };
    const retiro = posRetiroLineaDetalle(detalleId);
    if (retiro === "Bodega") {
      return {
        limite: parseFloat(cantidadEl.dataset.stockBodega || "0") || 0,
        etiqueta: "Excede stock en bodega",
      };
    }
    return {
      limite: parseFloat(cantidadEl.dataset.stockDisponible || "0") || 0,
      etiqueta: "Excede stock en tienda",
    };
  }

  function validarStockLinea(detalleId) {
    const cantidadEl = document.getElementById("cantidad_" + detalleId);
    if (!cantidadEl) return false;
    const rowApedido = document.getElementById("pos_row_" + detalleId);
    if (rowApedido && rowApedido.getAttribute("data-a-pedido") === "1") {
      const alertSkip = document.getElementById("stock_alert_" + detalleId);
      if (rowApedido) rowApedido.classList.remove("pos-row-stock-error");
      if (alertSkip) alertSkip.classList.add("d-none");
      return false;
    }
    const cantidad = parseFloat(cantidadEl.value) || 0;
    const factorStock = parseFloat(cantidadEl.dataset.factorStock || "1") || 1;
    const lim = posLimiteStockLinea(detalleId);
    const stockDisponible = lim.limite;
    const consumo = Math.max(0, Math.round(cantidad * factorStock));
    const excede = consumo > stockDisponible;

    const row = document.getElementById("pos_row_" + detalleId);
    const alertEl = document.getElementById("stock_alert_" + detalleId);
    const alertMsg = document.getElementById("stock_alert_msg_" + detalleId);
    const dispEl = document.getElementById("stock_disponible_" + detalleId);
    if (alertMsg) alertMsg.textContent = lim.etiqueta;
    if (dispEl) dispEl.textContent = String(stockDisponible);
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

  function mostrarPosToast(mensaje, opts) {
    opts = opts || {};
    const body = document.getElementById("posToastBody");
    if (!body) return;
    if (opts.html) {
      body.innerHTML = mensaje;
    } else {
      body.textContent = mensaje;
    }
    const toastEl = document.getElementById("posToast");
    if (!toastEl || typeof bootstrap === "undefined") return;
    toastEl.classList.remove(
      "text-bg-info",
      "text-bg-dark",
      "text-bg-danger",
      "text-bg-warning",
      "pos-toast--vale-success",
      "pos-toast--flash-warn",
      "pos-toast--flash-danger"
    );
    if (opts.variant === "vale" || opts.variant === "success") {
      toastEl.classList.add("pos-toast--vale-success");
    } else if (opts.variant === "danger") {
      toastEl.classList.add("text-bg-danger");
    } else if (opts.variant === "warning") {
      toastEl.classList.add("pos-toast--flash-warn");
    } else if (opts.variant === "info") {
      toastEl.classList.add("text-bg-info");
    } else {
      toastEl.classList.add("text-bg-dark");
    }
    const toast = bootstrap.Toast.getOrCreateInstance(toastEl, {
      delay: typeof opts.delay === "number" ? opts.delay : 1500,
      autohide: opts.autohide !== false,
    });
    toast.show();
  }

  function posParseValeFlashMessage(text) {
    const m = String(text || "").match(/Vale\s*N[°º#]?\s*(\d+)\s+emitido\s+para\s+(.+?)\.\s*Turno\s+(\d+)/i);
    if (!m) return null;
    return { id: m[1], cliente: m[2].trim(), turno: m[3] };
  }

  /** En pantalla vendedora: flash del servidor → toast premium (auto-cierra). */
  function posAbsorbServerFlashMessages() {
    if (!document.body.classList.contains("pos-pantalla-vendedora")) return;
    const main = document.querySelector(".app-main");
    if (!main) return;
    const alerts = main.querySelectorAll(":scope > .alert");
    if (!alerts.length) return;

    alerts.forEach(function (alertEl) {
      const text = (alertEl.textContent || "").replace(/\s+/g, " ").trim();
      const category = alertEl.classList.contains("alert-danger")
        ? "danger"
        : alertEl.classList.contains("alert-warning")
          ? "warning"
          : alertEl.classList.contains("alert-success")
            ? "success"
            : "info";
      const vale = posParseValeFlashMessage(text);
      if (vale) {
        const html =
          '<div class="pos-flash-toast">' +
          '<span class="pos-flash-toast__icon" aria-hidden="true"><i class="fas fa-check-circle"></i></span>' +
          '<div class="pos-flash-toast__text">' +
          '<strong class="pos-flash-toast__title">Vale emitido · N° ' +
          escapeHtmlPosJs(vale.id) +
          "</strong>" +
          '<span class="pos-flash-toast__meta">Turno ' +
          escapeHtmlPosJs(vale.turno) +
          " · " +
          escapeHtmlPosJs(vale.cliente) +
          "</span>" +
          "</div></div>";
        mostrarPosToast(html, { html: true, variant: "vale", delay: 5500 });
      } else if (text) {
        mostrarPosToast(text, {
          variant: category === "success" ? "vale" : category,
          delay: category === "danger" ? 6000 : 4200,
        });
      }
      alertEl.remove();
    });
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

  async function actualizarItem(detalleId, urlActualizarItem, opts) {
    opts = opts || {};
    if (posEsPantallaVendedora()) {
      const ajaxOpts = Object.assign({}, opts);
      if (!ajaxOpts.refrescar_carrito && !opts.supervisor_identificador && !opts.supervisor_tarjeta) {
        ajaxOpts.refrescar_carrito = false;
      }
      if (opts.supervisor_identificador || opts.supervisor_tarjeta) ajaxOpts.refrescar_carrito = true;
      return await posPersistirLineaAjax(detalleId, urlActualizarItem, ajaxOpts);
    }
    const cantidad = document.getElementById("cantidad_" + detalleId).value;
    const descuento = posDescuentoValorParaServidor(detalleId);
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

    if (opts.supervisor_tarjeta) {
      const ft = document.createElement("input");
      ft.type = "hidden";
      ft.name = "supervisor_tarjeta";
      ft.value = opts.supervisor_tarjeta;
      form.appendChild(ft);
    }
    if (opts.supervisor_pin) {
      const fpin = document.createElement("input");
      fpin.type = "hidden";
      fpin.name = "supervisor_pin";
      fpin.value = opts.supervisor_pin;
      form.appendChild(fpin);
    }
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

  function posUmbralPinDescuento() {
    const cfg = readPosConfig();
    const v = parseFloat(cfg && cfg.pos_descuento_umbral_pin_pct);
    return Number.isFinite(v) ? v : 20;
  }

  function descuentoRequierePinSupervisor(descNuevo) {
    return descNuevo > posUmbralPinDescuento() + EPS_DESC;
  }

  function posActualizarAutorizaPinVisible(detalleId) {
    const block = document.getElementById("posAutorizaPinBlock");
    const descEl = document.getElementById("descuento_" + detalleId);
    if (!block || !descEl) return;
    const descNuevo = posDescuentoPctDesdeInput(detalleId);
    const needPin = descuentoRequierePinSupervisor(descNuevo);
    block.classList.toggle("d-none", !needPin);
    const umbralEl = document.getElementById("posAutorizaUmbralText");
    if (umbralEl) umbralEl.textContent = String(Math.round(posUmbralPinDescuento()));
  }

  function productoCubreDescuentoPreautorizado(descEl, descNuevo) {
    if (!descEl) return false;
    if (descEl.dataset.productoDescuentoPreauth !== "1") return false;
    const maxPct = parseFloat(descEl.dataset.productoDescuentoPreauthMax || "0") || 0;
    if (descNuevo <= EPS_DESC) return true;
    if (maxPct <= EPS_DESC) return false;
    return descNuevo <= maxPct + EPS_DESC;
  }

  function descuentoRequiereCredencialSupervisor(detalleId, descLibre) {
    if (descLibre) return false;
    const descEl = document.getElementById("descuento_" + detalleId);
    if (!descEl) return false;
    const descNuevo = posDescuentoPctDesdeInput(detalleId);
    const descServidor = parseFloat(descEl.dataset.descuentoServidor || "0") || 0;
    // Sin cambio vs lo guardado: no volver a pedir tarjeta (finalizar_venta valida traza en BD).
    if (Math.abs(descNuevo - descServidor) <= EPS_DESC) {
      return false;
    }
    if (descNuevo <= EPS_DESC) {
      return false;
    }
    if (productoCubreDescuentoPreautorizado(descEl, descNuevo)) return false;
    return true;
  }

  function posAbrirModalAutorizacionDescuento(detalleId) {
    pendingDetalleIdAutorizacionDesc = detalleId;
    const modalAutorizaEl = document.getElementById("modalAutorizarDescuentoPos");
    if (modalAutorizaEl && typeof bootstrap !== "undefined") {
      posSearchPanelCerrar();
      posAnclarModalEnBody(modalAutorizaEl);
      posActualizarAutorizaPinVisible(detalleId);
      bootstrap.Modal.getOrCreateInstance(modalAutorizaEl).show();
      return true;
    }
    mostrarPosToast("No se pudo abrir la autorización. Recargue la página.");
    return false;
  }

  async function posIntentarGuardarLineaConAutorizacionDesc(detalleId, descLibre, urlActualizarItem, opts) {
    opts = opts || {};
    if (descuentoRequiereCredencialSupervisor(detalleId, descLibre)) {
      if (opts.cerrar_menu) posCerrarMenuDto(detalleId);
      if (!posAbrirModalAutorizacionDescuento(detalleId)) {
        const descEl = document.getElementById("descuento_" + detalleId);
        if (descEl) descEl.value = descEl.dataset.descuentoServidor || "0";
        posSyncDtoChip(detalleId);
      }
      return;
    }
    const ok = await actualizarItem(detalleId, urlActualizarItem, opts);
    if (ok && opts.cerrar_menu) posCerrarMenuDto(detalleId);
  }

  function posHayDescuentosSinGuardarOAutorizar(descLibre) {
    let hay = false;
    document.querySelectorAll(".descuento-input").forEach(function (inp) {
      const detalleId = inp.getAttribute("data-detalle-id");
      if (!detalleId) return;
      const servidor = parseFloat(inp.dataset.descuentoServidor || "0") || 0;
      const detId = inp.getAttribute("data-detalle-id");
      const nuevo = detId ? posDescuentoPctDesdeInput(detId) : parseFloat(inp.value || "0") || 0;
      if (Math.abs(nuevo - servidor) > EPS_DESC) {
        hay = true;
      }
    });
    return hay;
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
      cliente_id: cli.id,
      credito: cli.credito || null,
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
        if (
          resumen.credito &&
          resumen.credito.tiene_linea &&
          !document.body.classList.contains("pos-dock-relayout-busqueda")
        ) {
          html += posHtmlCreditoMetricas(resumen.credito);
        }
        extras.innerHTML = html;
      }
      posRenderCreditoCliente(resumen);
      setHiddenClienteField("cliente_rut", resumen.rut);
      setHiddenClienteField("cliente_nombre", resumen.nombre);
    } else if (posClienteUiEstado === "new") {
      const rutVal = (resumen && resumen.rut) || getClienteRutForSearch();
      setHiddenClienteField("cliente_rut", rutVal);
      openPosClienteNuevoModal(resumen || { rut: rutVal });
    } else if (posClienteUiEstado === "final") {
      setHiddenClienteField("cliente_rut", "");
      setHiddenClienteField("cliente_nombre", "");
      posRenderCreditoCliente(null);
    } else {
      posRenderCreditoCliente(null);
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

  function posPuedeVerCreditos() {
    const cfg = readPosConfig();
    return !!(cfg && cfg.puede_ver_creditos);
  }

  function posCreditoUrl(tipo, clienteId) {
    const cfg = readPosConfig();
    const tpl = cfg && cfg.credito_urls && cfg.credito_urls[tipo];
    if (!tpl || !clienteId) return null;
    return String(tpl).replace("__ID__", String(clienteId));
  }

  function posSyncCreditoChrome(resumen) {
    const boucher = document.getElementById("posBtnBoucher");
    if (!boucher) return;
    const id =
      resumen &&
      (resumen.cliente_id || (resumen.credito && resumen.credito.cliente_id));
    const puede = posPuedeVerCreditos();
    const btns = [{ el: boucher, tipo: "boucher" }];
    btns.forEach(function (b) {
      if (!b.el) return;
      const url = puede && id ? posCreditoUrl(b.tipo, id) : null;
      if (url) {
        b.el.href = url;
        b.el.classList.remove("disabled");
        b.el.removeAttribute("aria-disabled");
      } else {
        b.el.href = "#";
        b.el.classList.add("disabled");
        b.el.setAttribute("aria-disabled", "true");
      }
    });
  }

  function posHtmlCreditoMetricas(credito) {
    if (!credito || !credito.tiene_linea) return "";
    const bloqueado = !!credito.credito_bloqueado;
    const disp = Math.max(0, Number(credito.cupo_disponible || 0));
    const deuda = Number(credito.saldo_deudor || 0);
    const cupo = Number(credito.limite_credito || 0);
    let cls = "pos-credito-bar";
    if (bloqueado) cls += " pos-credito-bar--bloqueado";
    else if (disp < 50000) cls += " pos-credito-bar--bajo";
    let html =
      '<div class="' +
      cls +
      ' pos-credito-bar--dock">' +
      '<div class="pos-credito-bar__head"><i class="fas fa-credit-card" aria-hidden="true"></i> Crédito</div>' +
      '<div class="pos-credito-metrics">' +
      '<div class="pos-credito-chip"><span class="pos-credito-chip__label">Cupo</span><span class="pos-credito-chip__value">' +
      escapeHtmlPosJs(formatoCLP(cupo)) +
      "</span></div>" +
      '<div class="pos-credito-chip"><span class="pos-credito-chip__label">Deuda</span><span class="pos-credito-chip__value">' +
      escapeHtmlPosJs(formatoCLP(deuda)) +
      "</span></div>" +
      '<div class="pos-credito-chip pos-credito-chip--disp"><span class="pos-credito-chip__label">Disponible</span><span class="pos-credito-chip__value">' +
      escapeHtmlPosJs(formatoCLP(disp)) +
      "</span></div></div>";
    if (bloqueado) {
      html +=
        '<span class="badge rounded-pill text-bg-danger ms-1">Crédito suspendido</span>';
    }
    html += "</div>";
    return html;
  }

  function posRenderCreditoCliente(resumen) {
    const cred = resumen && resumen.credito;
    const credHtml = cred && cred.tiene_linea ? posHtmlCreditoMetricas(cred) : "";
    const relayout = document.body.classList.contains("pos-dock-relayout-busqueda");
    ["posCreditoStrip", "posDockCreditoStrip"].forEach(function (id) {
      const strip = document.getElementById(id);
      if (!strip) return;
      if (id === "posCreditoStrip" && relayout) {
        strip.innerHTML = "";
        strip.classList.add("d-none");
        return;
      }
      if (id === "posDockCreditoStrip" && !relayout) return;
      if (credHtml) {
        strip.innerHTML = credHtml;
        strip.classList.remove("d-none");
      } else {
        strip.innerHTML = "";
        strip.classList.add("d-none");
      }
    });
    posSyncCreditoChrome(resumen || null);
  }

  function posCreditoResumenFromCfg(cfg) {
    const ui = cfg && cfg.cliente_ui;
    if (ui && ui.estado === "known" && ui.resumen) return ui.resumen;
    return null;
  }

  function posHandleNuevaVentaChrome(urls) {
    const cfgNav = readPosConfig();
    const u = urls || (cfgNav && cfgNav.urls);
    if (!u || !u.nueva_venta) {
      mostrarPosToast("Nueva venta no disponible.", { variant: "danger" });
      return;
    }
    if (posContarItemsVale() <= 0) {
      mostrarPosToast("El carrito ya está vacío.", { variant: "info" });
      return;
    }
    if (
      !window.confirm(
        "¿Iniciar una venta nueva? El borrador actual (sin emitir) se descartará."
      )
    ) {
      return;
    }
    const btn = document.getElementById("posBtnNuevaVentaChrome");
    if (btn) btn.disabled = true;
    posIniciarNuevaVenta(u.nueva_venta).finally(function () {
      if (btn) btn.disabled = false;
    });
  }

  /** Menú header POS: enlazar siempre (antes de init pesado / early return). */
  function bindPosHeaderNavDock(cfg) {
    if (!document.body.classList.contains("pos-pantalla-vendedora")) return;

    const nav = document.querySelector(".pos-nav-dock");
    if (nav && nav.dataset.posNavDockBound !== "1") {
      nav.dataset.posNavDockBound = "1";
      nav.addEventListener(
        "click",
        function (e) {
          const cred = e.target.closest("#posBtnBoucher");
          if (!cred) return;
          const href = (cred.getAttribute("href") || "").trim();
          const off =
            cred.classList.contains("disabled") ||
            cred.getAttribute("aria-disabled") === "true" ||
            !href ||
            href === "#";
          if (off) {
            e.preventDefault();
            e.stopImmediatePropagation();
            mostrarPosToast(
              "Identifica un cliente con crédito para habilitar Boucher.",
              { variant: "info", delay: 2800 }
            );
          }
        },
        true
      );
    }

    const btnNueva = document.getElementById("posBtnNuevaVentaChrome");
    if (btnNueva && btnNueva.dataset.posNavDockBound !== "1") {
      btnNueva.dataset.posNavDockBound = "1";
      btnNueva.addEventListener("click", function () {
        posHandleNuevaVentaChrome(cfg && cfg.urls);
      });
    }

    posSyncCreditoChrome(posCreditoResumenFromCfg(cfg));
  }

  window.posSyncCreditoChrome = posSyncCreditoChrome;
  window.bindPosHeaderNavDock = bindPosHeaderNavDock;

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
    const cred = cv.credito;
    if (cred && cred.tiene_linea) {
      parts.push(
        '<span class="badge rounded-pill text-bg-primary"><i class="fas fa-credit-card me-1"></i>Disponible ' +
          escapeHtmlPosJs(formatoCLP(Math.max(0, Number(cred.cupo_disponible || 0)))) +
          "</span>"
      );
      if (Number(cred.saldo_deudor || 0) > 0) {
        parts.push(
          '<span class="badge rounded-pill text-bg-secondary"><i class="fas fa-file-invoice-dollar me-1"></i>Deuda ' +
            escapeHtmlPosJs(formatoCLP(Number(cred.saldo_deudor))) +
            "</span>"
        );
      }
    } else if (cv.credito_activo) {
      parts.push(
        '<span class="badge rounded-pill text-bg-success"><i class="fas fa-credit-card me-1"></i>Cliente con crédito</span>'
      );
    }
    if (cv.credito_bloqueado || (cred && cred.credito_bloqueado)) {
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
        const resumenCli = {
          nombre: posClienteCampoStr(data.cliente.nombre),
          rut: rut,
          saldo_favor: saldoFavor,
          cliente_id: data.cliente.id,
          credito: data.cliente.credito || null,
        };
        setPosClienteUiState("known", resumenCli);
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
    if (document.body.classList.contains("pos-pantalla-vendedora")) {
      if ("scrollRestoration" in history) {
        history.scrollRestoration = "manual";
      }
      window.scrollTo(0, 0);
      posSearchPanelLiberar();
      posAsegurarDockVisible();
    }
    posScrollRestaurar();
    posAbsorbServerFlashMessages();
    const cfg = readPosConfig();
    bindPosHeaderNavDock(cfg);
    if (!cfg || !cfg.urls) {
      return;
    }
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
        const compact = document.body.classList.contains("pos-pantalla-vendedora");
        crossSellToggleText.textContent = crossSellEnabled
          ? compact ? "Sugerencias" : "Sugerencias ON"
          : compact ? "Sugerencias off" : "Sugerencias OFF";
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
        const inputTarjeta = document.getElementById("posSupervisorTarjeta");
        const inputPin = document.getElementById("posSupervisorPin");
        const urlUsu = u.usuarios_autorizar_descuento;
        if (pendingDetalleIdAutorizacionDesc != null) {
          posActualizarAutorizaPinVisible(pendingDetalleIdAutorizacionDesc);
        }
        function postFetch() {
          posFiltrarMostrarSugerenciasSupervisor();
          if (inputTarjeta) inputTarjeta.focus();
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
        const tarjeta = document.getElementById("posSupervisorTarjeta");
        const pin = document.getElementById("posSupervisorPin");
        const pinBlock = document.getElementById("posAutorizaPinBlock");
        const wrap = document.getElementById("posSupervisorSuggestWrap");
        if (idEl) idEl.value = "";
        if (p) p.value = "";
        if (tarjeta) tarjeta.value = "";
        if (pin) pin.value = "";
        if (pinBlock) pinBlock.classList.add("d-none");
        if (wrap) {
          wrap.classList.add("d-none");
          wrap.innerHTML = "";
        }
      });
      const btnConf = document.getElementById("posConfirmarAutorizacionDescuento");
      if (btnConf) {
        btnConf.addEventListener("click", function () {
          const detalleId = pendingDetalleIdAutorizacionDesc;
          if (detalleId == null) return;
          const descEl = document.getElementById("descuento_" + detalleId);
          const descNuevo = descEl ? posDescuentoPctDesdeInput(detalleId) : 0;
          const tarjeta = ((document.getElementById("posSupervisorTarjeta") || {}).value || "").trim();
          const pin = ((document.getElementById("posSupervisorPin") || {}).value || "").trim();
          const ident = ((document.getElementById("posSupervisorIdentificador") || {}).value || "").trim();
          const pwd = (document.getElementById("posSupervisorClave") || {}).value || "";
          let opts = {};
          if (tarjeta) {
            if (descuentoRequierePinSupervisor(descNuevo) && pin.length !== 4) {
              mostrarPosToast("Ingrese PIN de 4 digitos del supervisor.");
              return;
            }
            opts = { supervisor_tarjeta: tarjeta, supervisor_pin: pin };
          } else if (ident && pwd) {
            opts = { supervisor_identificador: ident, supervisor_clave: pwd };
          } else {
            mostrarPosToast("Escanee la tarjeta del supervisor o use respaldo usuario/clave.");
            return;
          }
          pendingDetalleIdAutorizacionDesc = null;
          const modalInst = bootstrap.Modal.getInstance(modalAutorizaEl);
          if (modalInst) modalInst.hide();
          posCerrarMenuDto(detalleId);
          actualizarItem(detalleId, u.actualizar_item, Object.assign({ cerrar_menu: true }, opts)).then(
            function (ok) {
              if (ok) posCerrarMenuDto(detalleId);
            }
          );
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

    const MESES_ES_POS = [
      "enero", "febrero", "marzo", "abril", "mayo", "junio",
      "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre",
    ];
    const DIAS_ES_POS = [
      "Domingo", "Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado",
    ];

    function posDiasEntregaConfig() {
      const cfg = readPosConfig();
      const n = parseInt(cfg && cfg.pos_dias_entrega_a_pedido, 10);
      if (isNaN(n) || n < 1) return 5;
      return Math.min(n, 90);
    }

    function posSumarDiasHabiles(desde, dias) {
      const d = new Date(desde.getFullYear(), desde.getMonth(), desde.getDate());
      let added = 0;
      while (added < dias) {
        d.setDate(d.getDate() + 1);
        const wd = d.getDay();
        if (wd >= 1 && wd <= 5) added += 1;
      }
      return d;
    }

    function posFormatearFechaEntrega(d) {
      return DIAS_ES_POS[d.getDay()] + ", " + d.getDate() + " de " + MESES_ES_POS[d.getMonth()];
    }

    function posIsoFechaLocal(d) {
      const y = d.getFullYear();
      const m = String(d.getMonth() + 1).padStart(2, "0");
      const day = String(d.getDate()).padStart(2, "0");
      return y + "-" + m + "-" + day;
    }

    function posTieneLineasApedido() {
      return document.querySelectorAll('[data-a-pedido="1"]').length > 0;
    }

    function posRecogerLineasApedido() {
      const items = [];
      document.querySelectorAll('[data-a-pedido="1"]').forEach(function (row) {
        let detId = (row.getAttribute("data-detalle-id") || "").trim();
        if (!detId && row.id) detId = row.id.replace(/^pos_row_/, "");
        let nombre = (row.getAttribute("data-producto-nombre") || "").trim();
        if (!nombre) {
          const bold = row.querySelector(".fw-bold");
          if (bold) nombre = (bold.textContent || "").trim();
          else {
            const td = row.querySelector("td:nth-child(2)");
            if (td) nombre = (td.textContent || "").trim();
          }
        }
        const qtyEl = detId ? document.getElementById("cantidad_" + detId) : null;
        const cant = qtyEl ? parseInt(qtyEl.value, 10) || 1 : 1;
        items.push({ detalleId: detId, nombre: nombre, cantidad: cant });
      });
      return items;
    }

    function posTelefonoClienteParaCompromiso() {
      const hid = document.getElementById("cliente_telefono");
      if (hid && (hid.value || "").trim()) return hid.value.trim();
      return "";
    }

    const modalCompromisoEl = document.getElementById("modalCompromisoEntrega");
    const compromisoListaEl = document.getElementById("compromisoListaProductos");
    const compromisoFechaTextoEl = document.getElementById("compromisoFechaTexto");
    const compromisoTelefonoInput = document.getElementById("compromisoTelefonoInput");
    const compromisoNotificarWhatsapp = document.getElementById("compromisoNotificarWhatsapp");
    const compromisoRetiroTiendaRadio = document.getElementById("compromisoRetiroTienda");
    const compromisoDespachoRadio = document.getElementById("compromisoDespacho");
    const btnConfirmarCompromiso = document.getElementById("compromisoConfirmarBtn");
    let submitCompromisoConfirmado = false;
    let modalCompromisoInst = null;
    let fechaCompromisoCalculada = null;
    const modalPuntoRetiroElEarly = document.getElementById("modalConfirmarPuntoRetiro");
    [modalCompromisoEl, modalPuntoRetiroElEarly, document.getElementById("modalPosValeResume")].forEach(function (el) {
      if (el) posAnclarModalEnBody(el);
    });
    if (modalCompromisoEl && typeof bootstrap !== "undefined") {
      modalCompromisoInst = bootstrap.Modal.getOrCreateInstance(modalCompromisoEl);
    }

    function posProgramarTrasCerrarModal(modalEl, modalInst, fn) {
      if (!fn) return;
      if (modalEl && modalEl.classList.contains("show")) {
        modalEl.addEventListener("hidden.bs.modal", fn, { once: true });
        if (modalInst) modalInst.hide();
        return;
      }
      fn();
    }

    function posRequestEmitirValeForm(formEl) {
      if (formEl) formEl.requestSubmit();
    }

    function posRellenarModalCompromiso() {
      const dias = posDiasEntregaConfig();
      fechaCompromisoCalculada = posSumarDiasHabiles(new Date(), dias);
      if (compromisoFechaTextoEl) {
        compromisoFechaTextoEl.textContent =
          posFormatearFechaEntrega(fechaCompromisoCalculada) +
          " (" +
          dias +
          " día" +
          (dias === 1 ? "" : "s") +
          " hábil" +
          (dias === 1 ? "" : "es") +
          ")";
      }
      if (compromisoListaEl) {
        const lineas = posRecogerLineasApedido();
        compromisoListaEl.innerHTML = lineas
          .map(function (it) {
            return (
              '<li class="list-group-item px-0 py-2 d-flex justify-content-between gap-2">' +
              '<span class="text-truncate">' +
              escapeHtmlPosJs(it.nombre || "Producto") +
              "</span>" +
              '<span class="badge text-bg-info text-dark flex-shrink-0">×' +
              escapeHtmlPosJs(String(it.cantidad)) +
              "</span></li>"
            );
          })
          .join("");
        if (!lineas.length) {
          compromisoListaEl.innerHTML =
            '<li class="list-group-item text-muted">Sin líneas a pedido visibles.</li>';
        }
      }
      if (compromisoTelefonoInput) {
        compromisoTelefonoInput.value = posTelefonoClienteParaCompromiso();
      }
      if (compromisoRetiroTiendaRadio) compromisoRetiroTiendaRadio.checked = true;
      if (compromisoDespachoRadio) compromisoDespachoRadio.checked = false;
      if (compromisoNotificarWhatsapp) compromisoNotificarWhatsapp.checked = false;
    }

    function posAplicarCompromisoHiddens() {
      const hidOk = document.getElementById("compromisoConfirmado");
      const hidFecha = document.getElementById("compromisoFechaPrometida");
      const hidTel = document.getElementById("compromisoTelefonoHidden");
      const hidWa = document.getElementById("compromisoWhatsappHidden");
      const hidRetiro = document.getElementById("compromisoRetiroTiendaHidden");
      const hidDespacho = document.getElementById("compromisoDespachoHidden");
      if (hidOk) hidOk.value = "1";
      if (hidFecha && fechaCompromisoCalculada) {
        hidFecha.value = posIsoFechaLocal(fechaCompromisoCalculada);
      }
      const tel = compromisoTelefonoInput ? compromisoTelefonoInput.value.trim() : "";
      if (hidTel) hidTel.value = tel;
      const wa = compromisoNotificarWhatsapp && compromisoNotificarWhatsapp.checked;
      if (hidWa) hidWa.value = wa ? "1" : "0";
      const despacho = compromisoDespachoRadio && compromisoDespachoRadio.checked;
      if (hidDespacho) hidDespacho.value = despacho ? "1" : "0";
      if (hidRetiro) hidRetiro.value = despacho ? "0" : "1";
    }

    function posConfirmarCompromisoYContinuar() {
      if (btnConfirmarCompromiso && btnConfirmarCompromiso.disabled) return;
      posAplicarCompromisoHiddens();
      submitCompromisoConfirmado = true;
      const formEmitir = document.getElementById("formEmitirVale");
      if (btnConfirmarCompromiso) btnConfirmarCompromiso.disabled = true;
      posProgramarTrasCerrarModal(modalCompromisoEl, modalCompromisoInst, function () {
        if (btnConfirmarCompromiso) btnConfirmarCompromiso.disabled = false;
        posRequestEmitirValeForm(formEmitir);
      });
    }

    if (btnConfirmarCompromiso) {
      btnConfirmarCompromiso.addEventListener("click", posConfirmarCompromisoYContinuar);
    }
    if (modalCompromisoEl) {
      modalCompromisoEl.addEventListener("shown.bs.modal", function () {
        if (btnConfirmarCompromiso) btnConfirmarCompromiso.focus();
      });
      modalCompromisoEl.addEventListener("keydown", function (e) {
        if (e.key === "Enter" && modalCompromisoEl.classList.contains("show")) {
          e.preventDefault();
          posConfirmarCompromisoYContinuar();
        }
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
        if (btnConfirmarPuntoRetiro.disabled) return;
        if (!modalPuntoRetiroSelect || !puntoRetiroFormEl || !formEmitir) return;
        const valor = (modalPuntoRetiroSelect.value || "").trim();
        if (!valor || valor === "__PENDIENTE__") {
          if (modalPuntoRetiroError) modalPuntoRetiroError.classList.remove("d-none");
          return;
        }
        puntoRetiroFormEl.value = valor;
        submitConfirmadoDesdeModal = true;
        btnConfirmarPuntoRetiro.disabled = true;
        posProgramarTrasCerrarModal(modalPuntoRetiroEl, modalPuntoRetiroInst, function () {
          btnConfirmarPuntoRetiro.disabled = false;
          posRequestEmitirValeForm(formEmitir);
        });
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
        if (posHayDescuentosSinGuardarOAutorizar(descLibre)) {
          e.preventDefault();
          mostrarPosToast(
            "Hay descuentos sin autorización. Guarde cada línea con tarjeta/PIN del supervisor (botón ✓ o salga del campo %)."
          );
          return;
        }
        syncHiddenClienteFromPanels();
        aplicarClienteFinalSiRutOpcional();
        if (!validarRutCliente()) {
          e.preventDefault();
          return;
        }
        if (posTieneLineasApedido() && !submitCompromisoConfirmado) {
          e.preventDefault();
          posRellenarModalCompromiso();
          if (modalCompromisoInst) {
            posAnclarModalEnBody(modalCompromisoEl);
            modalCompromisoInst.show();
          } else {
            mostrarPosToast("Confirme el compromiso de entrega antes de emitir.");
          }
          return;
        }
        if (!submitConfirmadoDesdeModal && !puntoRetiroValido()) {
          e.preventDefault();
          sincronizarSelectPuntoRetiroEnModal();
          if (modalPuntoRetiroInst) {
            posAnclarModalEnBody(modalPuntoRetiroEl);
            modalPuntoRetiroInst.show();
          } else {
            mostrarPosToast("Seleccione punto de retiro antes de emitir.");
          }
          return;
        }
        submitConfirmadoDesdeModal = false;
        submitCompromisoConfirmado = false;
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
    } else if (posEsBusquedaUnificada()) {
      const inpUni = posInputBusqueda();
      if (inpUni) inpUni.focus();
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
        const inpManual = posInputBusqueda();
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
    const inpBuscarManual = posInputBusqueda();
    if (inpBuscarManual && u.buscar_producto) {
      posManualSearchApi = initPosManualSearch(u.buscar_producto);
    }

    wirePosFiltroBusquedaBotones(posManualSearchApi);
    wirePosValeResumePrompt(cfg);

    if ($("#buscarProducto").length && u.buscar_producto) {
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
              filtro_pos: posFiltroBusquedaActual(),
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

    const totalInicial = posTotalEfectivoDesdeDom(posLeerTotalClpDesdeMontoEl());

    document.querySelectorAll("[id^='precio_unitario_']").forEach(function (cell) {
      const valor = posReadClpFromEl(cell);
      const suf = (cell.textContent || "").indexOf("c/u") >= 0 ? " c/u" : "";
      posWriteClpToEl(cell, valor, suf);
    });
    document.querySelectorAll("[id^='subtotal_']").forEach(function (cell) {
      const valor = posReadClpFromEl(cell);
      posWriteClpToEl(cell, valor);
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

    posBindCartLineHandlers(u, descLibre);
    wirePosCartV2();

    actualizarEstadoEmisionVale();
    posAsegurarDockVisible();

    if (!window._posCartDeleteDelegado) {
      window._posCartDeleteDelegado = true;
      document.addEventListener("submit", function (e) {
        const form = e.target.closest(".pos-cart-card__delete-form");
        if (!form || !posEsPantallaVendedora()) return;
        const host = document.getElementById("posCartHost");
        if (!host || !host.contains(form)) return;
        e.preventDefault();
        posEliminarLineaCarrito(form);
      });
    }

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

    function posRenderHistorialHoy(items) {
      const list = document.getElementById("posHistorialHoyList");
      if (!list) return;
      if (!items || !items.length) {
        list.innerHTML =
          '<li class="list-group-item text-muted small border-0 px-0">Sin vales emitidos hoy.</li>';
        return;
      }
      list.innerHTML = items
        .map(function (it) {
          const st = String(it.estado || "").trim() || "—";
          const badge =
            st === "Pendiente"
              ? "text-bg-warning"
              : st === "Pagado"
                ? "text-bg-success"
                : "text-bg-secondary";
          return (
            '<li class="list-group-item border-0 px-0 py-1 d-flex justify-content-between align-items-center gap-2">' +
            '<span><span class="badge ' +
            badge +
            ' me-1">' +
            escapeHtmlPosJs(st) +
            "</span>" +
            '<span class="text-muted">' +
            escapeHtmlPosJs(it.hora || "") +
            "</span> · Vale #" +
            escapeHtmlPosJs(String(it.id)) +
            "</span>" +
            '<span class="pos-historial-total">' +
            escapeHtmlPosJs(it.total_fmt || "") +
            "</span></li>"
          );
        })
        .join("");
    }

    async function posCargarHistorialHoy() {
      const list = document.getElementById("posHistorialHoyList");
      const url = u && u.vales_hoy;
      if (!list || !url) return;
      try {
        const res = await fetch(url, { credentials: "same-origin", headers: { Accept: "application/json" } });
        const data = await res.json();
        if (data && data.ok) posRenderHistorialHoy(data.items || []);
        else posRenderHistorialHoy([]);
      } catch (_err) {
        list.innerHTML =
          '<li class="list-group-item text-danger small border-0 px-0">No se pudo cargar historial.</li>';
      }
    }

    const btnHistRefresh = document.getElementById("posHistorialRefresh");
    if (btnHistRefresh) btnHistRefresh.addEventListener("click", posCargarHistorialHoy);
    if (document.getElementById("posHistorialHoyList")) posCargarHistorialHoy();

    wirePosPedidosApedido(u);


  function posEmitirValeAtajo() {
    const btn = document.getElementById("emitirValeBtn");
    const formEmitir = document.getElementById("formEmitirVale");
    if (btn && !btn.disabled) {
      btn.click();
      return;
    }
    if (btn && btn.disabled && btn.title) {
      mostrarPosToast(btn.title, { delay: 2800, variant: "warning" });
      return;
    }
    if (posValeEstaVacio()) {
      mostrarPosToast("Agregue productos antes de emitir (F8).", { delay: 2200, variant: "warning" });
      return;
    }
    if (formEmitir) formEmitir.requestSubmit();
  }

    document.addEventListener("keydown", function (e) {
      if (e.key === "F2") {
        e.preventDefault();
        const inp = posInputBusqueda() || posInputEscaner();
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
        if (isTypingInField(e.target)) return;
        e.preventDefault();
        const cotUrl = u && u.cotizacion_nueva;
        if (cotUrl) window.location.href = cotUrl;
        else mostrarPosToast("Módulo cotizaciones no disponible.");
      }
      if (e.key === "F8") {
        if (isTypingInField(e.target)) return;
        e.preventDefault();
        posEmitirValeAtajo();
      }
    });
  });
})();

/**
 * LhexIA Academy — Mentor sidebar (POS + caja).
 * Expone initLhexiaMentorAcademy({ urls: { contexto, telemetria } }).
 */
(function () {
  "use strict";

  function escapeHtml(value) {
    return String(value == null ? "" : value)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  function renderPildoraCard(pill, priority) {
    if (!pill) return "";
    var titulo = escapeHtml(pill.titulo || pill.title || "Mentor");
    var cuerpo = escapeHtml(pill.mensaje_corto || pill.summary || "");
    var practicarHref = pill.practicar_href || pill.nav_href || "";
    var nav = practicarHref ? escapeHtml(practicarHref) : "";
    var dedupe =
      (pill.kpi_snapshot && pill.kpi_snapshot.pildora_dedupe_key) ||
      pill.dedupe_key ||
      (pill.kpi_snapshot && pill.kpi_snapshot.dedupe_key) ||
      "";
    var navBtn = nav
      ? '<a class="btn btn-sm btn-outline-info lhexia-mentor-glass-card__nav" href="' +
        nav +
        '" target="_blank" rel="noopener noreferrer"><i class="fas fa-bolt me-1"></i>Practicar ahora</a>'
      : "";
    return (
      '<article class="lhexia-mentor-glass-card' +
      (priority ? " lhexia-mentor-glass-card--priority" : "") +
      ' vertex-glass-card--mentor" data-mentor-node="vertex_mentor"' +
      (dedupe ? ' data-dedupe-key="' + escapeHtml(dedupe) + '"' : "") +
      ">" +
      '<div class="lhexia-mentor-glass-card__head">' +
      '<span class="lhexia-mentor-glass-card__icon"><i class="fas fa-graduation-cap"></i></span>' +
      '<span class="lhexia-mentor-glass-card__badge">Mentor · prioridad</span>' +
      "</div>" +
      '<h4 class="lhexia-mentor-glass-card__title">' +
      titulo +
      "</h4>" +
      (cuerpo ? '<p class="lhexia-mentor-glass-card__body">' + cuerpo + "</p>" : "") +
      navBtn +
      "</article>"
    );
  }

  function formatStepText(text) {
    if (window.LhexiaAcademyFormat) {
      return LhexiaAcademyFormat.formatAcademyRichText("- " + text)
        .replace(/^<ul class="lhexia-academy-list"><li>/, "")
        .replace(/<\/li><\/ul>$/, "");
    }
    return escapeHtml(text);
  }

  function renderGuideBody(guide) {
    var detalle = Array.isArray(guide.pasos_detalle) ? guide.pasos_detalle : [];
    if (detalle.length) {
      var dedupe = escapeHtml(guide.dedupe_key || "");
      return (
        '<ul class="lhexia-mentor-checklist lhexia-academy-rich">' +
        detalle
          .map(function (s) {
            var sid = escapeHtml(s.id || "");
            var checked = s.completed ? " checked" : "";
            return (
              '<li class="lhexia-mentor-checklist__item">' +
              '<label class="lhexia-mentor-checklist__label">' +
              '<input type="checkbox" class="lhexia-step-check" data-dedupe-key="' +
              dedupe +
              '" data-step-id="' +
              sid +
              '"' +
              checked +
              ">" +
              '<span class="lhexia-mentor-checklist__text">' +
              formatStepText(s.texto || "") +
              "</span>" +
              "</label></li>"
            );
          })
          .join("") +
        "</ul>"
      );
    }
    if (guide.content_html) {
      return '<div class="lhexia-academy-rich">' + guide.content_html + "</div>";
    }
    if (guide.content_markdown && window.LhexiaAcademyFormat) {
      return (
        '<div class="lhexia-academy-rich">' +
        LhexiaAcademyFormat.formatAcademyRichText(guide.content_markdown) +
        "</div>"
      );
    }
    var pasos = Array.isArray(guide.pasos) ? guide.pasos : [];
    if (!pasos.length) return "";
    return (
      '<ol class="lhexia-mentor-guide__steps lhexia-academy-rich">' +
      pasos
        .map(function (p) {
          return "<li>" + formatStepText(p) + "</li>";
        })
        .join("") +
      "</ol>"
    );
  }

  function renderGuide(guide) {
    var key = escapeHtml(guide.dedupe_key || "");
    var titulo = escapeHtml(guide.titulo || guide.title || "Guía");
    var bodyHtml = renderGuideBody(guide);
    var completeCls = guide.progress_complete ? " lhexia-mentor-guide--complete" : "";
    var ayuda = guide.ancla_ayuda
      ? '<a class="lhexia-mentor-guide__link" href="' +
        escapeHtml(guide.ancla_ayuda) +
        '" target="_blank" rel="noopener">Ver en manual completo</a>'
      : "";
    var practicar = guide.practicar_href
      ? '<a class="btn btn-sm btn-outline-info lhexia-mentor-practicar w-100 mt-2" href="' +
        escapeHtml(guide.practicar_href) +
        '" target="_blank" rel="noopener noreferrer"><i class="fas fa-bolt me-1"></i>Practicar ahora</a>'
      : "";
    return (
      '<div class="lhexia-mentor-guide' +
      completeCls +
      '" data-dedupe-key="' +
      key +
      '">' +
      '<button type="button" class="lhexia-mentor-guide__toggle" aria-expanded="false">' +
      "<span>" +
      titulo +
      "</span>" +
      '<i class="fas fa-chevron-down" aria-hidden="true"></i>' +
      "</button>" +
      '<div class="lhexia-mentor-guide__body">' +
      bodyHtml +
      practicar +
      ayuda +
      "</div>" +
      "</div>"
    );
  }

  function renderInvariante(data) {
    var el = document.getElementById("lhexiaMentorInvariante");
    if (!el) return;
    var txt =
      (data && data.invariante_financiera) ||
      (window.LhexiaAcademyFormat && LhexiaAcademyFormat.INVARIANTE_FINANCIERA) ||
      "";
    var show = txt && data && data.categoria_academy === "pos";
    if (!show) {
      el.classList.add("d-none");
      el.innerHTML = "";
      return;
    }
    el.classList.remove("d-none");
    el.innerHTML =
      '<div class="lhexia-academy-callout lhexia-academy-callout--invariante">' +
      '<i class="fas fa-shield-halved me-2" style="color:#ff5500;"></i>' +
      escapeHtml(txt) +
      "</div>";
  }

  function postTelemetria(url, dedupeKey, accion) {
    if (!url || !dedupeKey) return;
    fetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      credentials: "same-origin",
      body: JSON.stringify({
        dedupe_key: dedupeKey,
        accion: accion || "expandir",
        url: window.location.pathname + window.location.search,
      }),
    }).catch(function () {});
  }

  function resolveMentorUrls(urls) {
    urls = urls || {};
    return {
      contexto: urls.context || urls.contexto || "",
      telemetria: urls.log_read || urls.telemetria || "",
      save_step: urls.save_step || "",
    };
  }

  var _saveStepTimers = {};

  function postSaveStep(saveUrl, dedupeKey, stepId, checked) {
    if (!saveUrl || !dedupeKey || !stepId) return Promise.resolve();
    var tKey = dedupeKey + ":" + stepId;
    if (_saveStepTimers[tKey]) clearTimeout(_saveStepTimers[tKey]);
    return new Promise(function (resolve) {
      _saveStepTimers[tKey] = setTimeout(function () {
        fetch(saveUrl, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          credentials: "same-origin",
          body: JSON.stringify({
            dedupe_key: dedupeKey,
            step_id: stepId,
            checked: !!checked,
          }),
        })
          .then(function (r) {
            return r.json();
          })
          .then(function (data) {
            resolve(data);
          })
          .catch(function () {
            resolve(null);
          });
      }, 280);
    });
  }

  function bindChecklistHandlers(root, saveUrl) {
    if (!root || !saveUrl) return;
    root.querySelectorAll(".lhexia-step-check").forEach(function (cb) {
      cb.addEventListener("change", function () {
        var dedupe = cb.getAttribute("data-dedupe-key") || "";
        var stepId = cb.getAttribute("data-step-id") || "";
        var wrap = cb.closest(".lhexia-mentor-guide");
        postSaveStep(saveUrl, dedupe, stepId, cb.checked).then(function (data) {
          if (!data || !data.ok) return;
          if (wrap && data.all_complete) {
            wrap.classList.add("lhexia-mentor-guide--complete");
          } else if (wrap && !data.all_complete) {
            wrap.classList.remove("lhexia-mentor-guide--complete");
          }
        });
      });
    });
  }

  function extractDedupeFromPill(pill) {
    if (!pill) return "";
    var snap = pill.kpi_snapshot || {};
    return snap.pildora_dedupe_key || pill.dedupe_key || snap.dedupe_key || "";
  }

  function renderShortcuts(atajos) {
    var section = document.getElementById("lhexiaMentorShortcuts");
    var listEl = document.getElementById("lhexiaMentorShortcutsList");
    if (!section || !listEl) return;
    var list = Array.isArray(atajos) ? atajos : [];
    if (!list.length) {
      section.classList.add("d-none");
      listEl.innerHTML = "";
      return;
    }
    listEl.innerHTML = list
      .map(function (a) {
        var accion = a.accion || a.action || "";
        if (window.LhexiaAcademyFormat) {
          accion = LhexiaAcademyFormat.normalizarAtajosTexto(accion);
        }
        return (
          "<li><kbd>" +
          escapeHtml(a.tecla || a.key || "") +
          "</kbd><span>" +
          escapeHtml(accion) +
          "</span></li>"
        );
      })
      .join("");
    section.classList.remove("d-none");
  }

  function logCardsOnLoad(root, logUrl) {
    if (!root || !logUrl) return;
    root.querySelectorAll("[data-dedupe-key]").forEach(function (node) {
      var key = node.getAttribute("data-dedupe-key");
      if (key) postTelemetria(logUrl, key, "cargar");
    });
  }

  window.initLhexiaMentorAcademy = function initLhexiaMentorAcademy(opts) {
    opts = opts || {};
    var urls = resolveMentorUrls(opts.urls || {});
    var sidebar = document.getElementById("lhexia-mentor-sidebar");
    var fab = document.getElementById("lhexiaMentorFab");
    if (!sidebar || !fab) return;

    var backdrop = document.getElementById("lhexiaMentorBackdrop");
    var closeBtn = document.getElementById("lhexiaMentorClose");
    var loadingEl = document.getElementById("lhexiaMentorLoading");
    var priorityEl = document.getElementById("lhexiaMentorPriority");
    var libraryEl = document.getElementById("lhexiaMentorLibrary");
    var contextLoaded = false;
    var contextPayload = null;

    function setOpen(open) {
      sidebar.classList.toggle("is-open", !!open);
      sidebar.setAttribute("aria-hidden", open ? "false" : "true");
      fab.setAttribute("aria-expanded", open ? "true" : "false");
      document.body.classList.toggle("lhexia-mentor-sidebar-open", !!open);
    }

    function renderLibrary(guides) {
      if (!libraryEl) return;
      var list = Array.isArray(guides) ? guides : [];
      libraryEl.innerHTML = list.map(renderGuide).join("");
      libraryEl.querySelectorAll(".lhexia-mentor-guide__toggle").forEach(function (btn) {
        btn.addEventListener("click", function () {
          var wrap = btn.closest(".lhexia-mentor-guide");
          if (!wrap) return;
          var willOpen = !wrap.classList.contains("is-open");
          wrap.classList.toggle("is-open", willOpen);
          btn.setAttribute("aria-expanded", willOpen ? "true" : "false");
          if (willOpen) {
            var key = wrap.getAttribute("data-dedupe-key");
            postTelemetria(urls.telemetria, key, "expandir");
          }
        });
      });
      bindChecklistHandlers(libraryEl, urls.save_step);
    }

    function applyContext(data) {
      contextPayload = data || {};
      var pill = contextPayload.pildora_prioritaria;
      var art = contextPayload.articulo_principal;
      if (priorityEl) {
        if (art && (art.pasos_detalle || art.content_html)) {
          priorityEl.innerHTML = renderGuide(art);
          var artWrap = priorityEl.querySelector(".lhexia-mentor-guide");
          if (artWrap) artWrap.classList.add("is-open");
          bindChecklistHandlers(priorityEl, urls.save_step);
        } else {
          priorityEl.innerHTML = renderPildoraCard(pill || art, true);
        }
      }
      renderInvariante(contextPayload);
      renderShortcuts(contextPayload.atajos_teclado);
      renderLibrary(contextPayload.biblioteca);
      logCardsOnLoad(priorityEl, urls.telemetria);
      logCardsOnLoad(libraryEl, urls.telemetria);
      contextLoaded = true;
    }

    function loadContext(force) {
      if (!urls.contexto) return Promise.resolve();
      if (contextLoaded && !force) return Promise.resolve(contextPayload);
      if (loadingEl) loadingEl.classList.remove("d-none");
      var q =
        urls.contexto +
        (urls.contexto.indexOf("?") >= 0 ? "&" : "?") +
        "url=" +
        encodeURIComponent(window.location.pathname + window.location.search);
      return fetch(q, { credentials: "same-origin" })
        .then(function (r) {
          return r.json();
        })
        .then(function (data) {
          if (data && data.ok !== false) applyContext(data);
        })
        .catch(function () {
          if (priorityEl) {
            priorityEl.innerHTML =
              '<p class="small text-muted mb-0">No se pudo cargar el Mentor. Intente de nuevo.</p>';
          }
        })
        .finally(function () {
          if (loadingEl) loadingEl.classList.add("d-none");
        });
    }

    function openSidebar() {
      setOpen(true);
      loadContext(false);
    }

    fab.addEventListener("click", openSidebar);
    if (closeBtn) closeBtn.addEventListener("click", function () { setOpen(false); });
    if (backdrop) backdrop.addEventListener("click", function () { setOpen(false); });
    document.addEventListener("keydown", function (e) {
      if (e.key === "Escape" && sidebar.classList.contains("is-open")) setOpen(false);
    });
  };

  document.addEventListener("DOMContentLoaded", function () {
    if (!document.getElementById("lhexia-mentor-sidebar")) return;
    var cfgEl = document.getElementById("pos-config");
    if (!cfgEl || !cfgEl.textContent) return;
    try {
      var cfg = JSON.parse(cfgEl.textContent);
      if (cfg.urls && (cfg.urls.mentor_context || cfg.urls.mentor_contexto)) {
        window.initLhexiaMentorAcademy({
          urls: {
            context: cfg.urls.mentor_context || cfg.urls.mentor_contexto,
            log_read: cfg.urls.mentor_log_read || cfg.urls.mentor_telemetria,
            save_step: cfg.urls.mentor_save_step || cfg.urls.save_step || "",
            contexto: cfg.urls.mentor_context || cfg.urls.mentor_contexto,
            telemetria: cfg.urls.mentor_log_read || cfg.urls.mentor_telemetria,
          },
        });
      }
    } catch (e) { /* noop */ }
  });
})();

/** POS HUD — atenuar resto solo mientras el panel de sugerencias está abierto. */
(function () {
  "use strict";
  var FOCUS_CLASS = "pos-hud-search-focus";

  function searchInputs() {
    return [document.getElementById("posBuscarManual"), document.getElementById("posBarcodeWedge")].filter(
      Boolean
    );
  }

  function posSuggestPanelAbierto() {
    return !!document.querySelector(
      ".pos-unified-search-hero--suggest-open, .pos-manual-search-hero--suggest-open"
    );
  }

  function syncGlowFocus() {
    var focused = searchInputs().some(function (el) {
      return document.activeElement === el;
    });
    document.body.classList.toggle(FOCUS_CLASS, focused && posSuggestPanelAbierto());
  }

  window.posSyncHudSearchFocus = syncGlowFocus;

  document.addEventListener("DOMContentLoaded", function () {
    searchInputs().forEach(function (inp) {
      inp.addEventListener("focus", syncGlowFocus);
      inp.addEventListener("blur", function () {
        setTimeout(syncGlowFocus, 0);
      });
    });
    syncGlowFocus();
  });
})();
