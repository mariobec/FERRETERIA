/**
 * LhexIA Experience Wall — TV cliente: total + líneas en vivo; ticket térmico solo en esquina al emitir vale.
 */
(function () {
  "use strict";

  const snapEl = document.getElementById("ew-snap-config");
  if (!snapEl) return;

  let snapUrl;
  try {
    snapUrl = JSON.parse(snapEl.textContent || "{}").url || "";
  } catch (e) {
    return;
  }

  let lastPaintKey = "";
  let lastValeEmitShown = null;
  let valeCornerHideTimer = null;

  const fmt = (n) =>
    new Intl.NumberFormat("es-CL", {
      style: "currency",
      currency: "CLP",
      maximumFractionDigits: 0,
    }).format(Math.round(n || 0));

  const fmtTicketMiles = (n) =>
    String(Math.round(Number(n) || 0)).replace(/\B(?=(\d{3})+(?!\d))/g, ".");

  const esc = (s) =>
    String(s ?? "")
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/"/g, "&quot;");

  function padVale(n) {
    const v = parseInt(String(n || "0"), 10);
    let s = String(isNaN(v) ? 0 : v);
    while (s.length < 6) s = "0" + s;
    return s;
  }

  function truncName(str, max) {
    const t = String(str || "");
    return t.length <= max ? t : t.slice(0, Math.max(0, max - 1)) + "…";
  }

  function aplicarTokenTv(nuevoToken) {
    if (!nuevoToken) return;
    const u = new URL(window.location.href);
    if (u.searchParams.get("token") === nuevoToken) return;
    u.searchParams.set("token", nuevoToken);
    history.replaceState(null, "", u.toString());
    snapUrl = u.pathname + "?" + u.searchParams.toString();
  }

  function syncBarcode(folioStr, barcodeSvgId, barcodeOpts) {
    const svg = document.getElementById(barcodeSvgId || "ewTicketBarcode");
    if (!svg) return;
    const wrap = svg.closest(".ew-tk-barcode");
    if (!folioStr || typeof window.JsBarcode === "undefined") {
      if (wrap) wrap.style.display = "none";
      return;
    }
    if (wrap) wrap.style.display = "";
    const baseJs = {
      format: "CODE128",
      width: 1.85,
      height: clampPx(42, window.innerHeight * 0.06, 56),
      displayValue: true,
      fontSize: 11,
      margin: 4,
    };
    try {
      while (svg.firstChild) svg.removeChild(svg.firstChild);
      window.JsBarcode(svg, folioStr, Object.assign({}, baseJs, barcodeOpts || {}));
    } catch (_e) {}
  }

  function clampPx(lo, x, hi) {
    return Math.max(lo, Math.min(hi, x));
  }

  function defaultTvTicket(d) {
    const vv = (d.cliente_vitrina && !d.cliente_vitrina.es_cliente_final && d.cliente_vitrina.nombre_publico) || "";
    return {
      empresa: "Ferretería",
      fecha_hora_txt: "",
      caja_turno: 0,
      vendedor: "",
      punto_retiro: "Por confirmar",
      cliente_nombre: vv || "—",
      vale_folio: d.venta_id ? "VL" + padVale(d.venta_id) : "",
    };
  }

  function veToTvTicket(ve) {
    return {
      empresa: ve.empresa || "Ferretería",
      fecha_hora_txt: ve.fecha_hora_txt || "",
      caja_turno: ve.prioridad != null ? ve.prioridad : 0,
      vendedor: ve.usuario || "",
      punto_retiro: ve.punto_retiro || "Tienda",
      cliente_nombre: ve.cliente_nombre || "—",
      vale_folio: ve.venta_id ? "VL" + padVale(ve.venta_id) : "",
    };
  }

  function paintThermal(innerEl, tv, lineas, total, opts) {
    if (!innerEl || !tv) return;
    innerEl.className = "ew-ticket";
    opts = opts || {};
    const footerMode = opts.footerMode || "draft";
    const nameMax =
      opts.truncNameMax != null && opts.truncNameMax !== "" ? opts.truncNameMax : 28;
    const barcodeSvgId = opts.barcodeSvgId || "ewTicketBarcode";
    const headStrong =
      opts.headValeNum ||
      (opts.ventaId ? "VALE N° " + String(opts.ventaId) + " · borrador" : "");
    const rows =
      Array.isArray(lineas) && lineas.length
        ? lineas
            .map(function (ln) {
              const tag = (ln.retiro_tag || "[T]").trim();
              const name = truncName(ln.nombre, nameMax);
              return (
                "<tr>" +
                "<td>" +
                esc(tag + " " + name) +
                '</td><td class="ew-tk-ct">' +
                esc(String(ln.cantidad || 0)) +
                '</td><td class="ew-tk-pesos">' +
                esc(fmtTicketMiles(ln.subtotal || 0)) +
                "</td></tr>"
              );
            })
            .join("")
        : "";
    const bodyRows = rows
      ? rows
      : '<tr><td colspan="3" class="ew-tk-empty">Sin líneas aún · espere que carguen los productos</td></tr>';

    innerEl.innerHTML =
      '<div class="ew-tk-head">' +
      '<h2>✔ ' +
      esc(tv.empresa || "Ferretería") +
      "</h2></div>" +
      '<div class="ew-tk-info">' +
      (headStrong ? "<p><strong>" + esc(headStrong) + "</strong></p>" : "<p><strong>Vale · pantalla cliente</strong></p>") +
      "<p>" +
      esc(tv.fecha_hora_txt || "—") +
      "</p>" +
      "<p>Turno: " +
      esc(String(tv.caja_turno != null ? tv.caja_turno : 0)) +
      " · " +
      esc(tv.vendedor || "—") +
      "</p>" +
      "<p><strong>Retiro vale:</strong> " +
      esc(tv.punto_retiro || "—") +
      "</p>" +
      "<p>" +
      esc(tv.cliente_nombre || "—") +
      "</p>" +
      '<div class="ew-tk-barcode"><svg id="' +
      barcodeSvgId +
      '" aria-hidden="true"></svg></div>' +
      "</div>" +
      "<table><thead><tr><th>Producto</th><th class=\"ew-tk-ct\">Ct</th><th class=\"ew-tk-pesos\">$</th></tr></thead><tbody>" +
      bodyRows +
      "</tbody></table>" +
      '<div class="ew-tk-total">$' +
      esc(fmtTicketMiles(total || 0)) +
      "</div>" +
      (footerMode === "pendiente_caja"
        ? '<div class="ew-tk-foot ew-tk-foot--pending">*** PENDIENTE DE COBRO EN CAJA ***</div>'
        : '<div class="ew-tk-foot ew-tk-foot--draft">*** <strong>BORRADOR</strong> — TOTAL ESTIMADO — PAGO EN CAJA ***</div>');

    requestAnimationFrame(function () {
      syncBarcode(tv.vale_folio || "", barcodeSvgId, opts.barcodeOpts);
    });
  }

  function hideValeCorner() {
    const host = document.getElementById("ewValeCorner");
    if (!host) return;
    host.classList.remove("ew-vale-corner--visible");
    setTimeout(function () {
      host.classList.add("d-none");
      const inner = document.getElementById("ewValeCornerInner");
      if (inner) inner.innerHTML = "";
    }, 420);
  }

  function showValeCornerTicket(ve) {
    const host = document.getElementById("ewValeCorner");
    const inner = document.getElementById("ewValeCornerInner");
    if (!host || !inner) return;
    if (valeCornerHideTimer) {
      clearTimeout(valeCornerHideTimer);
      valeCornerHideTimer = null;
    }
    host.classList.remove("d-none");
    inner.innerHTML = "";
    requestAnimationFrame(function () {
      host.classList.add("ew-vale-corner--visible");
    });
    const tv = veToTvTicket(ve);
    paintThermal(inner, tv, ve.lineas || [], ve.total || 0, {
      footerMode: "pendiente_caja",
      headValeNum: "VALE N° " + String(ve.venta_id),
      ventaId: ve.venta_id,
      barcodeSvgId: "ewCornerBarcode",
      truncNameMax: 22,
      barcodeOpts: {
        width: 1.35,
        height: 38,
        displayValue: true,
        fontSize: 10,
        margin: 3,
      },
    });
    valeCornerHideTimer = setTimeout(function () {
      valeCornerHideTimer = null;
      hideValeCorner();
    }, 12000);
  }

  function renderGreeting(cv, abierta) {
    const el = document.getElementById("ewGreeting");
    if (!el) return;
    if (!abierta || !cv || cv.es_cliente_final) {
      el.classList.add("d-none");
      el.innerHTML = "";
      return;
    }
    let html = "";
    if (cv.nombre_publico) {
      html += "Hola, " + esc(cv.nombre_publico);
    } else {
      html += "Bienvenido";
    }
    const subs = [];
    if (cv.saldo_favor > 0) {
      subs.push("Tiene " + fmt(cv.saldo_favor) + " de saldo a favor");
    }
    if (cv.credito_activo) {
      subs.push("Compra con crédito habilitado");
    }
    if (cv.credito_bloqueado) {
      subs.push("Crédito no disponible — consulte en caja");
    }
    if (subs.length) {
      html += '<span class="ew-greeting-sub">' + esc(subs.join(" · ")) + "</span>";
    }
    el.innerHTML = html;
    el.classList.remove("d-none");
  }

  function renderValeEmitido(ve) {
    if (!ve || !ve.venta_id) return;
    if (lastValeEmitShown === ve.venta_id) return;
    lastValeEmitShown = ve.venta_id;

    showValeCornerTicket(ve);
  }

  function paintKeyFromSnap(d, lines, total, abierta) {
    const tv = d.tv_ticket ? Object.assign({}, d.tv_ticket) : defaultTvTicket(d);
    return [
      abierta ? "abierta" : d.estado,
      d.venta_id || "",
      total,
      (lines || []).map((x) => [x.id, x.cantidad, x.subtotal, x.retiro_tag].join(".")).join("|"),
      tv.fecha_hora_txt,
      tv.punto_retiro,
      tv.cliente_nombre || "",
    ].join("~");
  }

  /** Nombre para vitrina: ticket (nombre completo o «Cliente») o primer nombre vitrina. */
  function renderClienteBar(d, abierta) {
    const el = document.getElementById("ewClienteNombre");
    if (!el) return;
    if (!abierta) {
      el.classList.add("d-none");
      el.textContent = "";
      return;
    }
    const tv = d.tv_ticket || {};
    let nom = (tv.cliente_nombre && String(tv.cliente_nombre).trim()) || "";
    if (!nom || nom === "—") {
      const cv = d.cliente_vitrina;
      if (cv && cv.nombre_publico) {
        nom = String(cv.nombre_publico).trim();
      }
    }
    if (!nom || nom === "—") {
      el.classList.add("d-none");
      el.textContent = "";
      return;
    }
    el.textContent = nom;
    el.classList.remove("d-none");
  }

  function renderLiveProductLines(container, lineas) {
    if (!container) return;
    const arr = Array.isArray(lineas) ? lineas : [];
    if (!arr.length) {
      container.innerHTML = "";
      return;
    }
    container.innerHTML = arr
      .map(function (ln) {
        const id = ln.id != null ? String(ln.id) : "";
        const name = esc(truncName(ln.nombre, 96));
        const tag = esc(String((ln.retiro_tag || "").trim()));
        const qty = parseInt(String(ln.cantidad), 10) || 0;
        const subtot = fmt(ln.subtotal || 0);
        const pu = fmt(ln.precio_unitario || 0);
        const imgUrl = String(ln.imagen_url || "").trim();
        const thumb = imgUrl
          ? '<img class="ew-thumb" src="' +
            esc(imgUrl) +
            '" alt="" loading="lazy" referrerpolicy="no-referrer" />'
          : '<div class="ew-thumb-placeholder" aria-hidden="true"><i class="fas fa-box-open"></i></div>';
        const metaBits = [];
        if (tag) metaBits.push(tag);
        metaBits.push(pu + " c/u");
        return (
          '<div class="ew-line" data-linea-id="' +
          esc(id) +
          '"><div class="ew-thumb-wrap">' +
          thumb +
          '</div><div class="ew-line-body"><div class="ew-name">' +
          name +
          '</div><div class="ew-line-subrow"><span class="ew-meta">' +
          esc(metaBits.join(" · ")) +
          '</span><span class="ew-qty-badge">× ' +
          esc(String(qty)) +
          '</span></div></div><div class="ew-price">' +
          esc(subtot) +
          "</div></div>"
        );
      })
      .join("");
  }

  function bumpTotalEl(el) {
    if (!el) return;
    el.classList.remove("ew-total-bump");
    void el.offsetWidth;
    el.classList.add("ew-total-bump");
  }

  async function poll() {
    const sub = document.getElementById("ewSub");
    const thanks = document.getElementById("ewThanks");
    const shopping = document.getElementById("ewShopping");
    const itemsEl = document.getElementById("ewItems");
    const totalEl = document.getElementById("ewTotal");
    const idlePanel = document.getElementById("ewIdlePanel");
    const shell = document.getElementById("ewShell");
    if (!sub || !itemsEl || !totalEl) return;

    try {
      const r = await fetch(snapUrl, { credentials: "omit" });
      const d = await r.json();
      if (!d.ok) {
        if (d.error === "token_expirado") {
          sub.textContent = "Enlace expirado. Pida uno nuevo en el mostrador.";
        } else {
          sub.textContent = "No se pudo cargar la compra.";
        }
        return;
      }
      if (d.nuevo_token) aplicarTokenTv(d.nuevo_token);
      if (d.vale_emitido) renderValeEmitido(d.vale_emitido);

      const abierta = d.estado === "abierta";
      const sinVenta = d.estado === "sin_venta";
      const lines = abierta ? d.lineas || [] : [];
      const nItems = lines.length;
      const total = abierta ? d.total || 0 : 0;

      renderGreeting(d.cliente_vitrina, abierta);
      renderClienteBar(d, abierta);

      const showThanks = !abierta && !sinVenta;
      if (thanks) thanks.classList.toggle("d-none", !showThanks);
      if (shopping) shopping.classList.toggle("d-none", showThanks);

      if (shell) {
        shell.classList.toggle("ew-shell--dense-lines", abierta && nItems >= 4);
        shell.classList.toggle("ew-shell--compact-total", abierta && nItems >= 5);
        shell.classList.toggle("ew-shell--mega-dense", abierta && nItems >= 7);
      }

      if (sinVenta) {
        sub.textContent = "Esperando el siguiente pedido…";
        if (lastPaintKey !== "__sin_venta__") {
          lastPaintKey = "__sin_venta__";
          totalEl.textContent = fmt(0);
          renderLiveProductLines(itemsEl, []);
        }
        if (shell) {
          shell.classList.remove("ew-shell--dense-lines", "ew-shell--compact-total", "ew-shell--mega-dense");
        }
        if (idlePanel) idlePanel.classList.remove("d-none");
      } else if (abierta) {
        sub.textContent = nItems
          ? nItems +
            (nItems === 1
              ? " producto en su compra · total arriba"
              : " productos en su compra · total arriba")
          : "Aquí verá cada producto y el total mientras lo cargamos.";

        const pk = paintKeyFromSnap(d, lines, total, true);
        const changed = pk !== lastPaintKey;
        if (changed) {
          lastPaintKey = pk;
          totalEl.textContent = fmt(total);
          bumpTotalEl(totalEl);
          renderLiveProductLines(itemsEl, lines);
        }

        if (idlePanel) idlePanel.classList.toggle("d-none", nItems > 0);
      } else {
        sub.textContent = d.mensaje_cliente || "Venta finalizada.";
        lastPaintKey = "";
        if (shell) {
          shell.classList.remove("ew-shell--dense-lines", "ew-shell--compact-total", "ew-shell--mega-dense");
        }
        if (idlePanel) idlePanel.classList.add("d-none");
      }

      const txtThanks = document.getElementById("ewThanksText");
      if (txtThanks) txtThanks.textContent = d.mensaje_cliente || "¡Gracias por su compra!";

      const cat = document.getElementById("ewFoot");
      if (cat && d.catalogo_url) {
        cat.innerHTML =
          '<a href="' +
          esc(d.catalogo_url) +
          '" target="_blank" rel="noopener">' +
          '<i class="fas fa-store"></i> Ver catálogo en línea</a>';
      } else if (cat) {
        cat.innerHTML = "";
      }
    } catch (e) {
      sub.textContent = "Sin conexión momentánea. Reintentando…";
    }
  }

  window.addEventListener("pos-experience-wall-refresh", function () {
    poll();
  });

  document.getElementById("ewValeCornerClose")?.addEventListener("click", function () {
    if (valeCornerHideTimer) {
      clearTimeout(valeCornerHideTimer);
      valeCornerHideTimer = null;
    }
    hideValeCorner();
  });

  poll();
  setTimeout(poll, 300);
  setInterval(poll, 1500);
})();
