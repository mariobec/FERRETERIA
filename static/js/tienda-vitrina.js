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
    return appendMsg("<span>Buscando…</span>", "status");
  }

  function appendCards(cards) {
    if (!body || !Array.isArray(cards) || !cards.length) return;
    const wrap = document.createElement("div");
    wrap.className = "tienda-assistant-cards";
    cards.forEach(function (c) {
      const a = document.createElement("a");
      a.href = c.url || "#";
      a.innerHTML =
        "<strong>" +
        esc(c.nombre || "Producto") +
        "</strong><br>" +
        esc(c.precio_fmt || "") +
        " · " +
        (c.disponible ? "Disponible en tienda" : "Sin stock en tienda");
      wrap.appendChild(a);
    });
    body.appendChild(wrap);
    body.scrollTop = body.scrollHeight;
  }

  async function sendMessage(msg) {
    if (!cfg || !cfg.api_url || !msg) return;
    appendMsg(msg, "user");
    const statusEl = appendSearching();
    if (input) input.disabled = true;
    if (form) {
      const btn = form.querySelector("button[type='submit']");
      if (btn) btn.disabled = true;
    }
    try {
      const res = await fetch(cfg.api_url, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          mensaje: msg,
          producto_id: cfg.producto_id || null,
        }),
      });
      const data = await res.json();
      if (statusEl && statusEl.parentNode) statusEl.parentNode.removeChild(statusEl);
      if (!data || !data.ok) {
        appendMsg("No pude responder ahora. Intenta de nuevo en un momento.", "bot");
        return;
      }
      const reply = (data.reply || "Te ayudo con otra búsqueda.").trim();
      let extra = "";
      if (data.catalogo_url && !data.consulta) {
        extra =
          '<p class="small mb-0 mt-2"><a href="' +
          esc(data.catalogo_url) +
          '">Ver todos en el catálogo</a></p>';
      }
      appendMsg("<p class=\"mb-0\">" + esc(reply) + "</p>" + extra, "bot");
      if (data.consulta) {
        await actualizarGrillaCatalogo(data.consulta, data.catalogo_url);
      } else {
        appendCards(data.cards || []);
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

  if (toggle && panel) {
    toggle.addEventListener("click", function () {
      const open = panel.classList.toggle("d-none");
      const visible = !open;
      toggle.setAttribute("aria-expanded", visible ? "true" : "false");
      if (visible && input) input.focus();
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
    cartDrawer.classList.toggle("d-none", !open);
    cartBackdrop.classList.toggle("d-none", !open);
    cartToggle.setAttribute("aria-expanded", open ? "true" : "false");
    document.body.classList.toggle("tienda-cart-open", open);
  }

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

  function addToCart(item) {
    if (!item || !item.producto_id) return;
    const pid = parseInt(item.producto_id, 10);
    if (!pid) return;
    const lines = loadCart();
    let merged = false;
    for (let i = 0; i < lines.length; i++) {
      if (parseInt(lines[i].producto_id, 10) === pid) {
        const next = (parseInt(lines[i].cantidad, 10) || 1) + 1;
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
        cantidad: 1,
      });
    }
    saveCart(lines);
    if (!item.disponible) {
      showCartToast("Agregado. Sin stock en tienda — lo confirmamos al cotizar.");
    } else {
      showCartToast("Producto agregado al carrito");
    }
    setCartOpen(true);
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
      const addBtn = ev.target.closest("[data-add-carrito]");
      if (addBtn) {
        ev.preventDefault();
        const item = parseCarritoItem(addBtn);
        if (item) addToCart(item);
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
      if (ev.key === "Escape") setCartOpen(false);
    });
  }
})();
