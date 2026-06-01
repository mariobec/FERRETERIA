(function () {
  "use strict";

  const megaWrap = document.getElementById("tiendaMegaWrap");
  const btnMenu = document.getElementById("tiendaBtnMenu");
  const roots = document.querySelectorAll("[data-mega-root]");
  const panels = document.querySelectorAll("[data-mega-panel]");

  function setActiveRoot(vtexId) {
    roots.forEach(function (el) {
      el.classList.toggle("is-active", el.dataset.megaRoot === String(vtexId));
    });
    panels.forEach(function (el) {
      el.classList.toggle("is-visible", el.dataset.megaPanel === String(vtexId));
    });
  }

  roots.forEach(function (el) {
    el.addEventListener("mouseenter", function () {
      setActiveRoot(el.dataset.megaRoot);
    });
    el.addEventListener("focus", function () {
      setActiveRoot(el.dataset.megaRoot);
    });
  });

  if (btnMenu && megaWrap) {
    btnMenu.addEventListener("click", function () {
      megaWrap.classList.toggle("is-open");
      btnMenu.setAttribute(
        "aria-expanded",
        megaWrap.classList.contains("is-open") ? "true" : "false"
      );
    });
  }

  document.addEventListener("click", function (ev) {
    if (!megaWrap || !megaWrap.classList.contains("is-open")) return;
    if (megaWrap.contains(ev.target) || (btnMenu && btnMenu.contains(ev.target))) return;
    megaWrap.classList.remove("is-open");
    if (btnMenu) btnMenu.setAttribute("aria-expanded", "false");
  });

  const initial = document.querySelector(".tienda-mega-root.is-active");
  if (initial) setActiveRoot(initial.dataset.megaRoot);

  /* —— Liz asistente —— */
  const cfgEl = document.getElementById("tiendaAssistantConfig");
  const panel = document.getElementById("tiendaAssistantPanel");
  const toggle = document.getElementById("tiendaAssistantToggle");
  const resetBtn = document.getElementById("tiendaAssistantReset");
  const form = document.getElementById("tiendaAssistantForm");
  const input = document.getElementById("tiendaAssistantInput");
  const body = document.getElementById("tiendaAssistantBody");
  const chipsWrap = document.getElementById("tiendaAssistantChips");
  let cfg = null;
  let welcomeHtml = "";

  try {
    cfg = cfgEl ? JSON.parse(cfgEl.textContent || "{}") : null;
  } catch (_e) {
    cfg = null;
  }

  function esc(s) {
    const d = document.createElement("div");
    d.textContent = s == null ? "" : String(s);
    return d.innerHTML;
  }

  function saveWelcome() {
    if (!body) return;
    const w = body.querySelector("[data-welcome='1']");
    if (w) welcomeHtml = w.outerHTML;
  }

  saveWelcome();

  const LIZ_RESTORE_KEY = "tienda_liz_restore_v1";

  function guardarChatParaRestore() {
    if (!body) return;
    try {
      sessionStorage.setItem(
        LIZ_RESTORE_KEY,
        JSON.stringify({
          html: body.innerHTML,
          open: true,
        })
      );
    } catch (_e) {
      /* ignore quota / private mode */
    }
  }

  function restaurarChatSiHay() {
    let raw = null;
    try {
      raw = sessionStorage.getItem(LIZ_RESTORE_KEY);
    } catch (_e) {
      raw = null;
    }
    if (!raw || !body) return;
    try {
      const data = JSON.parse(raw);
      sessionStorage.removeItem(LIZ_RESTORE_KEY);
      if (data && data.html) {
        body.innerHTML = data.html;
        welcomeHtml = body.querySelector("[data-welcome='1']")
          ? body.querySelector("[data-welcome='1']").outerHTML
          : welcomeHtml;
      }
      if (data && data.open && panel && toggle) {
        panel.classList.remove("d-none");
        toggle.setAttribute("aria-expanded", "true");
      }
      body.scrollTop = body.scrollHeight;
    } catch (_e2) {
      sessionStorage.removeItem(LIZ_RESTORE_KEY);
    }
  }

  restaurarChatSiHay();

  function productoUrl(productoId) {
    if (!cfg || !cfg.slug) return "#";
    return "/tienda/" + cfg.slug + "/producto/" + parseInt(productoId, 10);
  }

  function renderTarjetaProducto(p) {
    const img = p.imagen_url
      ? '<img src="' + esc(p.imagen_url) + '" alt="" loading="lazy">'
      : '<i class="fas fa-image fa-2x text-muted"></i>';
    const marca = p.marca
      ? '<div class="tienda-card-brand">' + esc(p.marca) + "</div>"
      : "";
    const badge = p.disponible
      ? '<span class="tienda-badge ok">Disponible en tienda</span>'
      : '<span class="tienda-badge no">Sin stock en tienda</span>';
    const url = productoUrl(p.producto_id);
    const cartPayload = encodeURIComponent(
      JSON.stringify({
        producto_id: p.producto_id,
        nombre: p.nombre || "",
        referencia: p.referencia || "",
        precio: p.precio || 0,
        precio_fmt: p.precio_fmt || "",
        imagen_url: p.imagen_url || "",
        disponible: !!p.disponible,
        stock_tienda: p.stock_tienda || 0,
      })
    );
    return (
      '<article class="tienda-card">' +
      '<a href="' + esc(url) + '" class="tienda-card-img">' + img + "</a>" +
      '<div class="tienda-card-body">' +
      marca +
      '<h2 class="tienda-card-title"><a href="' + esc(url) + '">' + esc(p.nombre) + "</a></h2>" +
      '<div class="tienda-card-price">' + esc(p.precio_fmt || "") + "</div>" +
      badge +
      '<button type="button" class="tienda-card-add-cart" data-add-carrito="1" data-carrito-item="' +
      cartPayload +
      '"><i class="fas fa-cart-plus me-1"></i> Agregar</button>' +
      "</div></article>"
    );
  }

  function actualizarToolbarMeta(total, consulta) {
    const meta = document.getElementById("tiendaToolbarMeta");
    if (!meta) return;
    let txt = "<strong>" + esc(String(total || 0)) + "</strong> productos encontrados";
    if (consulta) txt += " · búsqueda «" + esc(consulta) + "»";
    meta.innerHTML = txt;
  }

  function limpiarFiltroCategoriaSidebar() {
    document.querySelectorAll(".tienda-sidebar-link.is-active").forEach(function (el) {
      el.classList.remove("is-active");
    });
    const strip = document.getElementById("tiendaSubcatsStrip");
    if (strip) strip.style.display = "none";
  }

  function syncBusquedaHeader(consulta) {
    const inp = document.querySelector(".tienda-search input[name='q']");
    if (inp) inp.value = consulta || "";
  }

  function syncUrlBusqueda(catalogoUrl) {
    if (!catalogoUrl) return;
    try {
      const target = new URL(catalogoUrl, window.location.origin);
      window.history.replaceState({}, "", target.pathname + target.search);
    } catch (_e) {
      /* ignore */
    }
  }

  function mostrarFranjaRecomendados(consulta, productos) {
    const hero = document.getElementById("tiendaLizHero");
    const sub = document.getElementById("tiendaLizHeroSub");
    if (!hero) return;
    if (!productos || !productos.length) {
      hero.classList.add("d-none");
      hero.setAttribute("aria-hidden", "true");
      return;
    }
    hero.classList.remove("d-none");
    hero.setAttribute("aria-hidden", "false");
    if (sub && consulta) {
      sub.textContent =
        "Resultados para «" + consulta + "» · precios de referencia y stock en tienda";
    }
  }

  function pintarGrillaCatalogo(data) {
    const area = document.getElementById("tiendaResultados");
    if (!area || !data) return;
    const productos = data.productos || [];
    const consulta = data.q || "";
    mostrarFranjaRecomendados(consulta, productos);
    let html = "";
    if (productos.length) {
      html = '<div class="tienda-grid" id="tiendaGrid">';
      productos.forEach(function (p) {
        html += renderTarjetaProducto(p);
      });
      html += "</div>";
    } else {
      html =
        '<p class="text-muted" id="tiendaGridEmpty">No hay productos para esta búsqueda. Prueba otra palabra.</p>';
    }
    area.innerHTML = html;
    actualizarToolbarMeta(data.total || productos.length, consulta);
    limpiarFiltroCategoriaSidebar();
    const hero = document.getElementById("tiendaLizHero");
    if (hero && productos.length) {
      hero.scrollIntoView({ behavior: "smooth", block: "start" });
    }
  }

  async function actualizarGrillaCatalogo(consulta, catalogoUrl) {
    const q = (consulta || "").trim();
    if (!q) return;
    const area = document.getElementById("tiendaResultados");
    if (!area || !cfg || !cfg.catalogo_api_url) {
      if (catalogoUrl) {
        guardarChatParaRestore();
        window.location.assign(catalogoUrl);
      }
      return;
    }
    area.classList.add("tienda-catalogo-loading");
    try {
      const url =
        cfg.catalogo_api_url + "?q=" + encodeURIComponent(q) + "&menu=0";
      const res = await fetch(url, { headers: { Accept: "application/json" } });
      const data = await res.json();
      if (!data || !data.ok) return;
      pintarGrillaCatalogo(data);
      syncBusquedaHeader(q);
      syncUrlBusqueda(catalogoUrl || ("/tienda/" + cfg.slug + "?q=" + encodeURIComponent(q) + "&menu=0"));
    } catch (_e) {
      if (catalogoUrl) {
        guardarChatParaRestore();
        window.location.assign(catalogoUrl);
      }
    } finally {
      area.classList.remove("tienda-catalogo-loading");
    }
  }

  function appendMsg(htmlOrText, kind) {
    if (!body) return null;
    const d = document.createElement("div");
    d.className = "tienda-assistant-msg " + (kind || "bot");
    if (kind === "user") {
      d.textContent = htmlOrText || "";
    } else {
      d.innerHTML = htmlOrText || "";
    }
    body.appendChild(d);
    body.scrollTop = body.scrollHeight;
    return d;
  }

  function appendSearching() {
    return appendMsg(
      '<div class="tienda-assistant-typing" aria-label="Liz está escribiendo">' +
      '<span class="tienda-assistant-typing-text">Liz está escribiendo</span>' +
      '<span class="tienda-assistant-typing-dots" aria-hidden="true">' +
      "<i></i><i></i><i></i>" +
      "</span>" +
      "</div>",
      "status"
    );
  }

  function carritoPayloadFromCard(c) {
    return {
      producto_id: c.producto_id,
      nombre: c.nombre || "",
      referencia: c.referencia || "",
      precio: parseInt(c.precio, 10) || 0,
      precio_fmt: c.precio_fmt || "",
      imagen_url: c.imagen_url || "",
      disponible: !!c.disponible,
      stock_tienda: parseInt(c.stock_tienda, 10) || 0,
    };
  }

  function appendProductCards(cards, parentEl) {
    if (!cards || !cards.length) return;
    const host = parentEl || body;
    if (!host) return;
    const wrap = document.createElement("div");
    wrap.className = "tienda-assistant-product-cards";
    cards.forEach(function (c) {
      const pid = parseInt(c.producto_id, 10);
      if (!pid) return;
      const img = c.imagen_url
        ? '<img src="' + esc(c.imagen_url) + '" alt="" class="tienda-assistant-pcard-img" loading="lazy">'
        : '<span class="tienda-assistant-pcard-img tienda-assistant-pcard-img--empty"><i class="fas fa-image"></i></span>';
      const badge = c.disponible
        ? '<span class="tienda-assistant-pcard-badge ok">Stock en tienda</span>'
        : '<span class="tienda-assistant-pcard-badge no">Consultar stock</span>';
      const payload = encodeURIComponent(JSON.stringify(carritoPayloadFromCard(c)));
      const art = document.createElement("article");
      art.className = "tienda-assistant-pcard";
      art.innerHTML =
        '<a href="' + esc(c.url || productoUrl(pid)) + '" class="tienda-assistant-pcard-media">' +
        img +
        "</a>" +
        '<div class="tienda-assistant-pcard-body">' +
        '<a href="' + esc(c.url || productoUrl(pid)) + '" class="tienda-assistant-pcard-title">' +
        esc(c.nombre || "Producto") +
        "</a>" +
        '<div class="tienda-assistant-pcard-price">' + esc(c.precio_fmt || "") + "</div>" +
        badge +
        '<button type="button" class="tienda-assistant-pcard-cart" data-add-carrito="1" data-carrito-item="' +
        payload +
        '"><i class="fas fa-cart-plus me-1"></i> Añadir al carrito</button>' +
        "</div>";
      wrap.appendChild(art);
    });
    host.appendChild(wrap);
    host.scrollTop = host.scrollHeight;
  }

  function appendCards(cards) {
    appendProductCards(cards, body);
  }

  function renderUiBlocks(ui, msgEl) {
    if (!ui || !Array.isArray(ui.blocks) || !ui.blocks.length) return false;
    const host = msgEl || body;
    if (!host) return false;
    ui.blocks.forEach(function (block) {
      if (!block || !block.type) return;
      if (block.type === "text") {
        if (block.text && msgEl) {
          /* texto principal ya va en el párrafo del mensaje bot */
        } else if (block.text && !msgEl) {
          appendMsg("<p class=\"mb-0\">" + esc(block.text) + "</p>", "bot");
        }
        return;
      }
      if (block.type === "product_cards") {
        appendProductCards(block.cards || [], host);
        return;
      }
      if (block.type === "button" && block.variant === "combo_cart") {
        const comboWrap = document.createElement("div");
        comboWrap.className = "tienda-assistant-combo-actions mt-2";
        const comboBtn = document.createElement("button");
        comboBtn.type = "button";
        comboBtn.className = "btn btn-sm btn-warning fw-semibold";
        comboBtn.setAttribute(
          "data-add-combo-carrito",
          encodeURIComponent(JSON.stringify(block.lineas || []))
        );
        comboBtn.innerHTML =
          '<i class="fas fa-cart-plus me-1"></i> ' + esc(block.label || "Agregar combo al carrito");
        comboWrap.appendChild(comboBtn);
        host.appendChild(comboWrap);
        return;
      }
      if (block.type === "cart_summary") {
        const box = document.createElement("div");
        box.className = "tienda-assistant-cart-cta";
        const sub = block.subtotal_fmt
          ? '<div class="tienda-assistant-cart-cta-sub">Subtotal ref. ' + esc(block.subtotal_fmt) + "</div>"
          : "";
        const action = block.cta_action || "generar_vale_web";
        const icon =
          action === "open_cart_whatsapp"
            ? '<i class="fab fa-whatsapp me-1"></i> '
            : '<i class="fas fa-receipt me-1"></i> ';
        box.innerHTML =
          sub +
          '<button type="button" class="tienda-assistant-cart-cta-btn" data-liz-cart-cta="' +
          esc(action) +
          '">' +
          icon +
          esc(block.cta_label || "Generar vale PED-WEB") +
          "</button>";
        host.appendChild(box);
        return;
      }
      if (block.type === "vale_emitido") {
        const box = document.createElement("div");
        box.className = "tienda-assistant-vale-ok";
        box.innerHTML =
          '<div class="tienda-assistant-vale-code">' +
          esc(block.ped_web_codigo || "") +
          "</div>" +
          '<div class="tienda-assistant-vale-meta">' +
          (block.vale_folio ? "Folio caja: " + esc(block.vale_folio) + " · " : "") +
          esc(block.monto_total_fmt || "") +
          "</div>" +
          '<p class="small mb-0 mt-2">' +
          esc(block.instrucciones || "Presenta este código en caja para retiro.") +
          "</p>";
        host.appendChild(box);
        return;
      }
      if (block.type === "link" && block.url) {
        const p = document.createElement("p");
        p.className = "small mb-0 mt-2";
        p.innerHTML =
          '<a href="' + esc(block.url) + '">' + esc(block.label || "Ver catálogo") + "</a>";
        host.appendChild(p);
      }
    });
    host.scrollTop = host.scrollHeight;
    return true;
  }

  function snapshotCarritoParaApi() {
    if (typeof window.__tiendaGetCarrito === "function") {
      return window.__tiendaGetCarrito();
    }
    return [];
  }

  async function sendMessage(msg) {
    if (!cfg || !cfg.api_url || !msg) return;
    if (typeof setCartOpen === "function") setCartOpen(false);
    appendMsg(msg, "user");
    const statusEl = appendSearching();
    if (input) input.disabled = true;
    if (form) {
      const btn = form.querySelector("button[type='submit']");
      if (btn) btn.disabled = true;
    }
    const contactoPayload = function () {
      const nomEl = document.getElementById("tiendaCartNombre");
      const telEl = document.getElementById("tiendaCartTelefono");
      return {
        cliente_nombre: nomEl ? nomEl.value.trim() : "",
        cliente_telefono: telEl ? telEl.value.trim() : "",
      };
    };
    try {
      const res = await fetch(cfg.api_url, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(
          Object.assign(
            {
              mensaje: msg,
              producto_id: cfg.producto_id || null,
              carrito: snapshotCarritoParaApi(),
            },
            contactoPayload()
          )
        ),
      });
      let data = null;
      try {
        data = await res.json();
      } catch (_jsonErr) {
        data = null;
      }
      if (statusEl && statusEl.parentNode) statusEl.parentNode.removeChild(statusEl);
      if (!res.ok || !data || !data.ok) {
        const det = (data && (data.mensaje || data.error)) || ("HTTP " + res.status);
        appendMsg(
          "No pude responder ahora (" + esc(String(det).slice(0, 120)) + "). Intenta de nuevo.",
          "bot"
        );
        return;
      }
      const reply = (data.reply || "Te ayudo con otra búsqueda.").trim();
      const msgEl = appendMsg("<p class=\"mb-0\">" + esc(reply) + "</p>", "bot");
      const ui = data.ui;
      const uiHandled =
        ui && renderUiBlocks(ui, msgEl);
      if (!uiHandled) {
        if (data.catalogo_url && !data.consulta) {
          const p = document.createElement("p");
          p.className = "small mb-0 mt-2";
          p.innerHTML =
            '<a href="' + esc(data.catalogo_url) + '">Ver todos en el catálogo</a>';
          if (msgEl) msgEl.appendChild(p);
        }
        if (data.modo_combo && data.combo_lineas && data.combo_lineas.length && msgEl) {
          const comboWrap = document.createElement("div");
          comboWrap.className = "tienda-assistant-combo-actions mt-2";
          const comboBtn = document.createElement("button");
          comboBtn.type = "button";
          comboBtn.className = "btn btn-sm btn-warning fw-semibold";
          comboBtn.setAttribute(
            "data-add-combo-carrito",
            encodeURIComponent(JSON.stringify(data.combo_lineas))
          );
          comboBtn.innerHTML =
            '<i class="fas fa-cart-plus me-1"></i> Agregar combo al carrito';
          comboWrap.appendChild(comboBtn);
          msgEl.appendChild(comboWrap);
        }
        appendCards(data.cards || []);
        if (data.modo_combo && data.combo_cards && data.combo_cards.length) {
          appendCards(data.combo_cards);
        }
      }
      const actualizarGrilla =
        data.consulta &&
        (!ui || ui.actualizar_grilla !== false);
      if (actualizarGrilla) {
        await actualizarGrillaCatalogo(data.consulta, data.catalogo_url);
      }
    } catch (_err) {
      if (statusEl && statusEl.parentNode) statusEl.parentNode.removeChild(statusEl);
      appendMsg("No pude conectar con Liz. Revisa tu conexión e intenta otra vez.", "bot");
    } finally {
      if (input) {
        input.disabled = false;
        input.focus();
      }
      if (form) {
        const btn = form.querySelector("button[type='submit']");
        if (btn) btn.disabled = false;
      }
    }
  }

  function resetChat() {
    if (!body) return;
    body.innerHTML = welcomeHtml || "";
    if (input) input.focus();
  }

  function setLizOpen(open) {
    if (!panel || !toggle) return;
    panel.classList.toggle("d-none", !open);
    toggle.setAttribute("aria-expanded", open ? "true" : "false");
    document.body.classList.toggle("tienda-assistant-open", open);
    if (open && input) input.focus();
  }

  if (toggle && panel) {
    toggle.addEventListener("click", function () {
      const willOpen = panel.classList.contains("d-none");
      if (willOpen && typeof window.__tiendaSetCartOpen === "function") {
        window.__tiendaSetCartOpen(false);
      }
      setLizOpen(willOpen);
    });
  }

  if (resetBtn) {
    resetBtn.addEventListener("click", resetChat);
  }

  if (chipsWrap) {
    chipsWrap.addEventListener("click", function (ev) {
      const btn = ev.target.closest(".tienda-assistant-chip");
      if (!btn) return;
      const text = (btn.getAttribute("data-chip") || btn.textContent || "").trim();
      if (text) sendMessage(text);
    });
  }

  if (form && input && cfg && cfg.api_url) {
    form.addEventListener("submit", function (ev) {
      ev.preventDefault();
      const msg = (input.value || "").trim();
      if (!msg) return;
      input.value = "";
      sendMessage(msg);
    });
  }

  /* —— Carrito vitrina (localStorage + WhatsApp) —— */
  const cartCfgEl = document.getElementById("tiendaCarritoConfig");
  const cartToggle = document.getElementById("tiendaCartToggle");
  const cartBackdrop = document.getElementById("tiendaCartBackdrop");
  const cartDrawer = document.getElementById("tiendaCartDrawer");
  const cartClose = document.getElementById("tiendaCartClose");
  const cartCount = document.getElementById("tiendaCartCount");
  const cartEmpty = document.getElementById("tiendaCartEmpty");
  const cartLines = document.getElementById("tiendaCartLines");
  const cartFooter = document.getElementById("tiendaCartFooter");
  const cartSubtotal = document.getElementById("tiendaCartSubtotal");
  const cartWhatsapp = document.getElementById("tiendaCartWhatsapp");
  const cartVaciar = document.getElementById("tiendaCartVaciar");
  const cartNombre = document.getElementById("tiendaCartNombre");
  const cartTelefono = document.getElementById("tiendaCartTelefono");
  const cartToast = document.getElementById("tiendaCartToast");
  let cartCfg = null;
  let cartToastTimer = null;

  try {
    cartCfg = cartCfgEl ? JSON.parse(cartCfgEl.textContent || "{}") : null;
  } catch (_cartE) {
    cartCfg = null;
  }

  function parseCarritoItem(el) {
    const raw = el.getAttribute("data-carrito-item");
    if (!raw) return null;
    try {
      return JSON.parse(decodeURIComponent(raw));
    } catch (_e1) {
      try {
        return JSON.parse(raw);
      } catch (_e2) {
        return null;
      }
    }
  }

  function loadCart() {
    if (!cartCfg || !cartCfg.storage_key) return [];
    try {
      const raw = localStorage.getItem(cartCfg.storage_key);
      const data = raw ? JSON.parse(raw) : [];
      return Array.isArray(data) ? data : [];
    } catch (_e) {
      return [];
    }
  }

  function saveCart(lines) {
    if (!cartCfg || !cartCfg.storage_key) return;
    try {
      localStorage.setItem(cartCfg.storage_key, JSON.stringify(lines || []));
    } catch (_e) {
      /* quota */
    }
    renderCart();
  }

  function cartMaxQty() {
    const n = parseInt(cartCfg && cartCfg.max_qty, 10);
    return n > 0 ? n : 99;
  }

  function calcSubtotal(lines) {
    let sub = 0;
    let units = 0;
    (lines || []).forEach(function (ln) {
      const qty = Math.max(1, Math.min(parseInt(ln.cantidad, 10) || 1, cartMaxQty()));
      const precio = parseInt(ln.precio, 10) || 0;
      sub += precio * qty;
      units += qty;
    });
    return { subtotal: sub, units: units };
  }

  function fmtClp(n) {
    try {
      return new Intl.NumberFormat("es-CL", {
        style: "currency",
        currency: "CLP",
        maximumFractionDigits: 0,
      }).format(n);
    } catch (_e) {
      return "$" + String(n);
    }
  }

  function showCartToast(msg) {
    if (!cartToast) return;
    cartToast.textContent = msg;
    cartToast.classList.remove("d-none");
    if (cartToastTimer) clearTimeout(cartToastTimer);
    cartToastTimer = setTimeout(function () {
      cartToast.classList.add("d-none");
    }, 2600);
  }

  function setCartOpen(open) {
    if (!cartDrawer || !cartBackdrop || !cartToggle) return;
    if (open) {
      setLizOpen(false);
    }
    cartDrawer.classList.toggle("d-none", !open);
    cartBackdrop.classList.toggle("d-none", !open);
    cartToggle.setAttribute("aria-expanded", open ? "true" : "false");
    document.body.classList.toggle("tienda-cart-open", open);
  }

  window.__tiendaSetCartOpen = setCartOpen;

  function renderCart() {
    const lines = loadCart();
    const tot = calcSubtotal(lines);
    if (cartCount) {
      if (tot.units > 0) {
        cartCount.textContent = String(tot.units);
        cartCount.classList.remove("d-none");
      } else {
        cartCount.classList.add("d-none");
      }
    }
    if (!cartLines || !cartEmpty || !cartFooter) return;
    if (!lines.length) {
      cartEmpty.classList.remove("d-none");
      cartLines.classList.add("d-none");
      cartFooter.classList.add("d-none");
      cartLines.innerHTML = "";
      if (cartSubtotal) cartSubtotal.textContent = fmtClp(0);
      if (cartWhatsapp) cartWhatsapp.classList.add("disabled");
      return;
    }
    cartEmpty.classList.add("d-none");
    cartLines.classList.remove("d-none");
    cartFooter.classList.remove("d-none");
    if (cartWhatsapp) cartWhatsapp.classList.remove("disabled");
    let html = "";
    lines.forEach(function (ln) {
      const pid = parseInt(ln.producto_id, 10);
      const qty = Math.max(1, Math.min(parseInt(ln.cantidad, 10) || 1, cartMaxQty()));
      const thumb = ln.imagen_url
        ? '<img src="' + esc(ln.imagen_url) + '" alt="" class="tienda-cart-line-img">'
        : '<span class="tienda-cart-line-img tienda-cart-line-img--empty"><i class="fas fa-image"></i></span>';
      const stockNote = ln.disponible
        ? ""
        : '<span class="tienda-cart-line-warn">Sin stock en tienda</span>';
      html +=
        '<li class="tienda-cart-line" data-cart-pid="' +
        pid +
        '">' +
        thumb +
        '<div class="tienda-cart-line-info">' +
        '<div class="tienda-cart-line-name">' +
        esc(ln.nombre || "Producto") +
        "</div>" +
        '<div class="tienda-cart-line-meta">' +
        esc(ln.precio_fmt || "") +
        (ln.referencia ? " · Ref. " + esc(ln.referencia) : "") +
        stockNote +
        "</div>" +
        '<div class="tienda-cart-line-qty">' +
        '<button type="button" class="tienda-cart-qty-btn" data-cart-qty="' +
        pid +
        '" data-delta="-1" aria-label="Menos">−</button>' +
        '<span class="tienda-cart-qty-val">' +
        qty +
        "</span>" +
        '<button type="button" class="tienda-cart-qty-btn" data-cart-qty="' +
        pid +
        '" data-delta="1" aria-label="Más">+</button>' +
        '<button type="button" class="tienda-cart-remove" data-cart-remove="' +
        pid +
        '" aria-label="Quitar"><i class="fas fa-trash-alt"></i></button>' +
        "</div></div></li>";
    });
    cartLines.innerHTML = html;
    if (cartSubtotal) cartSubtotal.textContent = fmtClp(tot.subtotal);
  }

  function mergeCartLine(lines, item, increment) {
    if (!item || !item.producto_id) return lines;
    const pid = parseInt(item.producto_id, 10);
    if (!pid) return lines;
    const addQty = Math.max(1, parseInt(item.cantidad, 10) || 1);
    let merged = false;
    for (let i = 0; i < lines.length; i++) {
      if (parseInt(lines[i].producto_id, 10) === pid) {
        const base = parseInt(lines[i].cantidad, 10) || 1;
        const next = increment ? base + addQty : Math.max(base, addQty);
        lines[i].cantidad = Math.min(next, cartMaxQty());
        merged = true;
        break;
      }
    }
    if (!merged) {
      lines.push({
        producto_id: pid,
        nombre: item.nombre || "Producto",
        referencia: item.referencia || "",
        precio: parseInt(item.precio, 10) || 0,
        precio_fmt: item.precio_fmt || "",
        imagen_url: item.imagen_url || "",
        disponible: !!item.disponible,
        stock_tienda: parseInt(item.stock_tienda, 10) || 0,
        cantidad: Math.min(addQty, cartMaxQty()),
      });
    }
    return lines;
  }

  function addToCart(item, qty) {
    if (!item || !item.producto_id) return;
    const payload = Object.assign({}, item);
    if (qty != null) payload.cantidad = qty;
    const lines = mergeCartLine(loadCart(), payload, !qty);
    saveCart(lines);
    if (!item.disponible) {
      showCartToast("Agregado. Sin stock en tienda — lo confirmamos al cotizar.");
    } else {
      showCartToast("Producto agregado al carrito");
    }
    setCartOpen(true);
  }

  function replaceCart(lineas) {
    const safe = Array.isArray(lineas) ? lineas : [];
    saveCart(
      safe.map(function (ln) {
        return {
          producto_id: parseInt(ln.producto_id, 10),
          nombre: ln.nombre || "Producto",
          referencia: ln.referencia || "",
          precio: parseInt(ln.precio, 10) || 0,
          precio_fmt: ln.precio_fmt || "",
          imagen_url: ln.imagen_url || "",
          disponible: !!ln.disponible,
          stock_tienda: parseInt(ln.stock_tienda, 10) || 0,
          cantidad: Math.max(1, Math.min(parseInt(ln.cantidad, 10) || 1, cartMaxQty())),
        };
      }).filter(function (ln) { return ln.producto_id > 0; })
    );
  }

  function addComboToCart(lineas) {
    if (!lineas || !lineas.length) return;
    let lines = loadCart();
    let added = 0;
    lineas.forEach(function (item) {
      const before = lines.length;
      lines = mergeCartLine(lines, item, false);
      if (lines.length >= before) added += 1;
    });
    saveCart(lines);
    showCartToast(
      added > 1 ? "Combo agregado al carrito (" + added + " productos)" : "Combo agregado al carrito"
    );
    setCartOpen(false);
    if (typeof setLizOpen === "function") setLizOpen(true);
    if (input) input.focus();
  }

  function changeQty(pid, delta) {
    const lines = loadCart();
    const out = [];
    lines.forEach(function (ln) {
      if (parseInt(ln.producto_id, 10) !== pid) {
        out.push(ln);
        return;
      }
      const next = (parseInt(ln.cantidad, 10) || 1) + delta;
      if (next >= 1) {
        ln.cantidad = Math.min(next, cartMaxQty());
        out.push(ln);
      }
    });
    saveCart(out);
  }

  function removeLine(pid) {
    saveCart(
      loadCart().filter(function (ln) {
        return parseInt(ln.producto_id, 10) !== pid;
      })
    );
  }

  async function enviarWhatsapp() {
    const lines = loadCart();
    if (!lines.length) {
      showCartToast("El carrito está vacío");
      return;
    }
    if (!cartCfg || !cartCfg.whatsapp_api_url) {
      showCartToast("WhatsApp no configurado en la tienda");
      return;
    }
    if (cartWhatsapp) cartWhatsapp.classList.add("disabled");
    try {
      const res = await fetch(cartCfg.whatsapp_api_url, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          lineas: lines,
          cliente_nombre: cartNombre ? cartNombre.value.trim() : "",
          cliente_telefono: cartTelefono ? cartTelefono.value.trim() : "",
        }),
      });
      const data = await res.json();
      if (!data || !data.ok || !data.url) {
        showCartToast("No se pudo armar el pedido. Intenta de nuevo.");
        return;
      }
      window.open(data.url, "_blank", "noopener,noreferrer");
      showCartToast("Abriendo WhatsApp con tu pedido…");
    } catch (_err) {
      showCartToast("Error de conexión. Revisa tu red.");
    } finally {
      if (cartWhatsapp) cartWhatsapp.classList.remove("disabled");
    }
  }

  window.__tiendaGetCarrito = function () {
    return loadCart();
  };

  window.tiendaCarritoConfig = cartCfg;
  window.tiendaCarritoAdd = addToCart;
  window.tiendaCarritoReplace = replaceCart;
  window.tiendaGenerarValePedido = generarValePedidoWeb;

  async function generarValePedidoWeb() {
    const lines = loadCart();
    if (!lines.length) {
      showCartToast("Agrega productos al carrito primero");
      return;
    }
    const api = cartCfg && cartCfg.vale_api_url;
    if (!api) {
      showCartToast("Generación de vale no disponible");
      return;
    }
    showCartToast("Generando vale PED-WEB…");
    try {
      const res = await fetch(api, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          lineas: lines,
          cliente_nombre: cartNombre ? cartNombre.value.trim() : "",
          cliente_telefono: cartTelefono ? cartTelefono.value.trim() : "",
        }),
      });
      const data = await res.json();
      if (!data || !data.ok) {
        showCartToast((data && data.mensaje) || "No se pudo generar el vale");
        return;
      }
      if (body && data.ui) {
        const msgEl = appendMsg(
          "<p class=\"mb-0\">" + esc(data.mensaje || data.reply || "Vale generado.") + "</p>",
          "bot"
        );
        renderUiBlocks(data.ui, msgEl);
        setLizOpen(true);
      } else if (data.ped_web_codigo) {
        appendMsg(
          "<p class=\"mb-0\">Vale <strong>" +
            esc(data.ped_web_codigo) +
            "</strong> creado. Preséntalo en caja.</p>",
          "bot"
        );
        setLizOpen(true);
      }
      showCartToast("Vale " + (data.ped_web_codigo || "") + " listo");
    } catch (_valeErr) {
      showCartToast("Error de conexión al generar vale");
    }
  }

  if (cartCfg && cartToggle) {
    renderCart();
    cartToggle.addEventListener("click", function () {
      const open = cartDrawer && cartDrawer.classList.contains("d-none");
      setCartOpen(!!open);
    });
    if (cartClose) cartClose.addEventListener("click", function () { setCartOpen(false); });
    if (cartBackdrop) cartBackdrop.addEventListener("click", function () { setCartOpen(false); });
    if (cartVaciar) {
      cartVaciar.addEventListener("click", function () {
        saveCart([]);
        showCartToast("Carrito vacío");
      });
    }
    if (cartWhatsapp) {
      cartWhatsapp.addEventListener("click", function (ev) {
        ev.preventDefault();
        enviarWhatsapp();
      });
    }
    document.addEventListener("click", function (ev) {
      const comboBtn = ev.target.closest("[data-add-combo-carrito]");
      if (comboBtn) {
        ev.preventDefault();
        const raw = comboBtn.getAttribute("data-add-combo-carrito");
        if (!raw) return;
        try {
          const lineas = JSON.parse(decodeURIComponent(raw));
          addComboToCart(lineas);
        } catch (_comboErr) {
          showCartToast("No pude cargar el combo. Intenta de nuevo.");
        }
        return;
      }
      const lizCta = ev.target.closest("[data-liz-cart-cta]");
      if (lizCta) {
        ev.preventDefault();
        const action = lizCta.getAttribute("data-liz-cart-cta") || "generar_vale_web";
        if (action === "open_cart_whatsapp") {
          setCartOpen(true);
          if (cartWhatsapp && !cartWhatsapp.classList.contains("disabled")) {
            cartWhatsapp.focus();
          }
        } else {
          generarValePedidoWeb();
        }
        return;
      }
      const addBtn = ev.target.closest("[data-add-carrito]");
      if (addBtn) {
        ev.preventDefault();
        const item = parseCarritoItem(addBtn);
        if (item) {
          const lines = mergeCartLine(loadCart(), item, true);
          saveCart(lines);
          if (!item.disponible) {
            showCartToast("Agregado. Sin stock en tienda — lo confirmamos al cotizar.");
          } else {
            showCartToast("Producto agregado al carrito");
          }
          if (addBtn.closest(".tienda-assistant-pcard")) {
            setCartOpen(false);
            setLizOpen(true);
            if (input) input.focus();
          } else {
            setCartOpen(true);
          }
        }
        return;
      }
      const qtyBtn = ev.target.closest("[data-cart-qty]");
      if (qtyBtn) {
        ev.preventDefault();
        changeQty(parseInt(qtyBtn.getAttribute("data-cart-qty"), 10), parseInt(qtyBtn.getAttribute("data-delta"), 10));
        return;
      }
      const rm = ev.target.closest("[data-cart-remove]");
      if (rm) {
        ev.preventDefault();
        removeLine(parseInt(rm.getAttribute("data-cart-remove"), 10));
      }
    });
    document.addEventListener("keydown", function (ev) {
      if (ev.key === "Escape") {
        setCartOpen(false);
        setLizOpen(false);
      }
    });
  }
})();
