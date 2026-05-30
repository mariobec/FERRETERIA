/**
 * LhexIA Experience Wall — TV cliente: total + líneas en vivo; ticket térmico solo en esquina al emitir vale.
 */
(function () {
  "use strict";

  const snapEl = document.getElementById("ew-snap-config");
  if (!snapEl) return;

  let snapUrl;
  let logoUrl = "/static/img/lhexia-icon-hex-login.png";
  let vitrinaImgTest = false;
  try {
    const snapCfg = JSON.parse(snapEl.textContent || "{}");
    snapUrl = snapCfg.url || "";
    if (snapCfg.logoUrl) logoUrl = snapCfg.logoUrl;
    vitrinaImgTest = !!snapCfg.vitrinaImgTest;
  } catch (e) {
    return;
  }

  function vitrinaImgTestFromUrl() {
    try {
      const p = new URL(window.location.href).searchParams;
      for (const key of ["vitrina_img_test", "vitrina_test", "img_test", "test"]) {
        const v = (p.get(key) || "").trim().toLowerCase();
        if (v === "1" || v === "true" || v === "yes" || v === "on") return true;
      }
    } catch (e) {
      /* noop */
    }
    return false;
  }

  function ensureSnapUrlImgTest() {
    if (!vitrinaImgTest || !snapUrl) return;
    try {
      const u = new URL(snapUrl, window.location.origin);
      u.searchParams.set("vitrina_img_test", "1");
      snapUrl = u.pathname + u.search;
    } catch (e) {
      /* noop */
    }
  }

  function ensureImgTestBanner() {
    if (!vitrinaImgTest) return;
    let b = document.getElementById("ewImgTestBanner");
    if (!b) {
      b = document.createElement("div");
      b.id = "ewImgTestBanner";
      b.className = "ew-img-test-banner";
      b.setAttribute("role", "status");
      b.textContent =
        "MODO PRUEBA · Imágenes SVG de diagnóstico (si se ven bien, el carrusel OK — revisar fotos catálogo)";
      document.body.insertBefore(b, document.body.firstChild);
    }
  }

  vitrinaImgTest = vitrinaImgTest || vitrinaImgTestFromUrl();
  ensureSnapUrlImgTest();
  ensureImgTestBanner();

  const vitrina = globalThis.EwVitrinaCarousel;
  if (vitrina) vitrina.setLogoUrl(logoUrl);

  let lastPaintKey = "";
  let lastRecoPaintKey = "";
  let lastValeEmitShown = null;
  let lastThanksValeId = null;
  let valeCornerHideTimer = null;
  let postThanksSince = null;
  let postEmitVale = null;
  let thanksTimer = null;
  /** vitrina | cart | thanks */
  let ewPhase = "vitrina";
  let vitrinaOnScreen = false;
  let thanksVitrinaPaused = false;
  const POST_THANKS_VITRINA_MS = 4000;
  const RECO_CAROUSEL_MS = 5200;
  let recoCarouselItems = [];
  let recoCarouselIdx = 0;
  let recoCarouselTimer = null;
  let recoCarouselSig = "";

  function msSinceThanks() {
    return postThanksSince ? Date.now() - postThanksSince : 0;
  }

  function inThanksPhase() {
    return ewPhase === "thanks" && postThanksSince !== null && msSinceThanks() < POST_THANKS_VITRINA_MS;
  }

  function vitrinaPayload(d) {
    return d && d.vitrina_attract ? d.vitrina_attract : null;
  }

  function vitrinaReady(d) {
    const va = vitrinaPayload(d);
    return !!(va && va.activo && va.escenas && va.escenas.length);
  }

  function scheduleThanksToVitrina() {
    if (thanksTimer) clearTimeout(thanksTimer);
    thanksTimer = setTimeout(function () {
      thanksTimer = null;
      ewPhase = "vitrina";
      poll();
    }, POST_THANKS_VITRINA_MS);
  }

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

  function shortMotivo(text, maxLen) {
    maxLen = maxLen || 68;
    var s = String(text || "").trim();
    if (!s) return "";
    if (s.length <= maxLen) return s;
    var cut = s.slice(0, maxLen - 1);
    var sp = cut.lastIndexOf(" ");
    if (sp > maxLen * 0.55) cut = cut.slice(0, sp);
    return cut.trim() + "\u2026";
  }

  function truncName(str, max) {
    const t = String(str || "");
    return t.length <= max ? t : t.slice(0, Math.max(0, max - 1)) + "…";
  }

  function aplicarTokenTv(nuevoToken) {
    if (!nuevoToken) return;
    try {
      const api = new URL(snapUrl, window.location.origin);
      if (api.searchParams.get("token") === nuevoToken) return;
      api.searchParams.set("token", nuevoToken);
      snapUrl = api.pathname + api.search;
      const page = new URL(window.location.href);
      page.searchParams.set("token", nuevoToken);
      history.replaceState(null, "", page.toString());
    } catch (e) {
      /* noop */
    }
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

  function clienteNombreVitrina(d) {
    const tv = d.tv_ticket || {};
    let nom = (tv.cliente_nombre && String(tv.cliente_nombre).trim()) || "";
    if (!nom || nom === "—") {
      const cv = d.cliente_vitrina;
      if (cv && cv.nombre_publico) nom = String(cv.nombre_publico).trim();
    }
    return nom && nom !== "—" ? nom : "";
  }

  function clienteIdentificado(d, cv) {
    if (cv && cv.es_cliente_final) return false;
    return !!clienteNombreVitrina(d);
  }

  function renderCfmHeader(d, abierta) {
    const hello = document.getElementById("ewHello");
    const saldoBadge = document.getElementById("ewSaldoBadge");
    const credBadge = document.getElementById("ewCreditoBadge");
    const credFoot = document.getElementById("ewCreditoFoot");
    const cv = d.cliente_vitrina;

    if (hello) {
      if (!abierta || !clienteIdentificado(d, cv)) {
        hello.classList.add("d-none");
        hello.textContent = "¡Hola!";
      } else {
        hello.textContent = "¡Hola, " + clienteNombreVitrina(d) + "!";
        hello.classList.remove("d-none");
      }
    }

    if (saldoBadge) {
      if (abierta && cv && !cv.es_cliente_final && (cv.saldo_favor || 0) > 0) {
        saldoBadge.textContent = "Saldo a favor: " + fmt(cv.saldo_favor);
        saldoBadge.classList.remove("d-none");
      } else {
        saldoBadge.classList.add("d-none");
        saldoBadge.textContent = "";
      }
    }

    if (credBadge) {
      const showCred =
        abierta && cv && !cv.es_cliente_final && cv.credito_activo && !cv.credito_bloqueado;
      if (showCred) {
        credBadge.textContent = "Compra con crédito habilitado";
        credBadge.classList.remove("d-none");
      } else {
        credBadge.classList.add("d-none");
        credBadge.textContent = "";
      }
    }

    if (credFoot) {
      const cred = cv && cv.credito;
      if (abierta && cred && cred.tiene_linea && cred.cupo_disponible != null) {
        credFoot.textContent =
          "Crédito disponible: " + fmt(cred.cupo_disponible);
        credFoot.classList.remove("d-none");
      } else if (abierta && cv && cv.saldo_favor > 0) {
        credFoot.textContent = "Saldo a favor: " + fmt(cv.saldo_favor);
        credFoot.classList.remove("d-none");
      } else {
        credFoot.classList.add("d-none");
        credFoot.textContent = "";
      }
    }
  }

  function recoPaintKey(d, abierta) {
    const rec = d.recomendaciones;
    if (!abierta) return "off:" + (d.estado || "");
    if (!rec || !Array.isArray(rec.items) || !rec.items.length) {
      return "empty:" + (d.venta_id || "");
    }
    const itemsSig = rec.items
      .slice(0, 8)
      .map(function (it) {
        return [it.id, it.precio, it.nombre, it.motivo, it.imagen_url || ""].join(":");
      })
      .join("|");
    return [rec.titulo || "", rec.subtitulo || "", itemsSig].join("~");
  }

  function stopRecoCarousel() {
    if (recoCarouselTimer !== null) {
      clearTimeout(recoCarouselTimer);
      recoCarouselTimer = null;
    }
  }

  function armRecoProgress() {
    const bar = document.getElementById("ewRecoProgressBar");
    if (!bar) return;
    bar.style.setProperty("--ew-reco-dur", RECO_CAROUSEL_MS + "ms");
    bar.classList.remove("is-running");
    void bar.offsetWidth;
    bar.classList.add("is-running");
  }

  function paintRecoDots() {
    const dotsEl = document.getElementById("ewRecoDots");
    if (!dotsEl) return;
    const n = recoCarouselItems.length;
    if (n <= 1) {
      dotsEl.innerHTML = "";
      dotsEl.classList.add("d-none");
      return;
    }
    dotsEl.classList.remove("d-none");
    let html = "";
    for (let i = 0; i < n; i++) {
      html +=
        '<span class="' +
        (i === recoCarouselIdx ? "is-active" : "") +
        '" aria-hidden="true"></span>';
    }
    dotsEl.innerHTML = html;
  }

  function showRecoSlide(nextIdx, armProgress) {
    if (!recoCarouselItems.length) return;
    recoCarouselIdx =
      ((nextIdx % recoCarouselItems.length) + recoCarouselItems.length) %
      recoCarouselItems.length;
    const slides = document.querySelectorAll(".ew-cfm-reco-slide");
    for (let i = 0; i < slides.length; i++) {
      slides[i].classList.toggle("is-active", i === recoCarouselIdx);
    }
    paintRecoDots();
    if (armProgress !== false) armRecoProgress();
  }

  function scheduleRecoCarousel() {
    stopRecoCarousel();
    if (recoCarouselItems.length <= 1) {
      armRecoProgress();
      return;
    }
    armRecoProgress();
    recoCarouselTimer = globalThis.setTimeout(function () {
      recoCarouselTimer = null;
      showRecoSlide(recoCarouselIdx + 1, false);
      scheduleRecoCarousel();
    }, RECO_CAROUSEL_MS);
  }

  function buildRecoMediaHtml(imgUrl) {
    const inner = imgUrl
      ? '<img class="ew-cfm-reco-card__img" src="' +
        esc(imgUrl) +
        '" alt="" loading="eager" decoding="async" referrerpolicy="no-referrer" />'
      : '<div class="ew-cfm-reco-card__img ew-cfm-reco-card__img--ph" aria-hidden="true"><i class="fas fa-screwdriver-wrench"></i></div>';
    return (
      '<div class="ew-cfm-reco-card__media">' +
      '<div class="ew-cfm-reco-card__ambient" aria-hidden="true">' +
      '<span class="ew-cfm-reco-card__orb ew-cfm-reco-card__orb--a"></span>' +
      '<span class="ew-cfm-reco-card__orb ew-cfm-reco-card__orb--b"></span>' +
      '<span class="ew-cfm-reco-card__spot"></span></div>' +
      '<div class="ew-cfm-reco-card__stage">' +
      '<div class="ew-cfm-reco-card__halo" aria-hidden="true"></div>' +
      '<div class="ew-cfm-reco-card__frame">' +
      '<div class="ew-cfm-reco-card__frame-ring" aria-hidden="true"></div>' +
      '<div class="ew-cfm-reco-card__img-frame">' +
      inner +
      "</div>" +
      '<div class="ew-cfm-reco-card__shine" aria-hidden="true"></div></div>' +
      '<div class="ew-cfm-reco-card__pedestal" aria-hidden="true"></div></div></div>'
    );
  }

  function buildRecoCardHtml(it) {
    const imgUrl = String(it.imagen_url || "").trim();
    const media = buildRecoMediaHtml(imgUrl);
    const motivo = shortMotivo(it.motivo, 90);
    const motivoHtml = motivo
      ? '<p class="ew-cfm-reco-card__motivo">' + esc(motivo) + "</p>"
      : "";
    return (
      '<article class="ew-cfm-reco-card">' +
      media +
      '<div class="ew-cfm-reco-card__body">' +
      '<p class="ew-cfm-reco-card__name">' +
      esc(truncName(it.nombre, 64)) +
      "</p>" +
      motivoHtml +
      "</div>" +
      '<footer class="ew-cfm-reco-card__foot">' +
      '<p class="ew-cfm-reco-card__price">' +
      esc(fmt(it.precio || 0)) +
      '</p><span class="ew-cfm-reco-card__btn" aria-hidden="true">Pida en mostrador</span></footer></article>'
    );
  }

  function mountRecoCarousel(items) {
    const root = document.getElementById("ewRecoCards");
    if (!root) return;
    const list = items.slice(0, 8);
    const sig = list
      .map(function (it) {
        return [it.id, it.precio, it.nombre, it.motivo, it.imagen_url || ""].join(":");
      })
      .join("|");
    if (sig === recoCarouselSig && root.querySelector(".ew-cfm-reco-slide")) {
      return;
    }
    stopRecoCarousel();
    recoCarouselSig = sig;
    recoCarouselItems = list;
    recoCarouselIdx = 0;
    root.classList.remove("d-none");
    root.classList.add("ew-cfm-reco-carousel--live");
    root.innerHTML =
      '<div class="ew-cfm-reco-slides">' +
      list
        .map(function (it, idx) {
          return (
            '<div class="ew-cfm-reco-slide' +
            (idx === 0 ? " is-active" : "") +
            '">' +
            buildRecoCardHtml(it) +
            "</div>"
          );
        })
        .join("") +
      '</div><div id="ewRecoDots" class="ew-cfm-reco-dots d-none" aria-hidden="true"></div>' +
      '<div class="ew-cfm-reco-progress"><span id="ewRecoProgressBar" class="ew-cfm-reco-progress__bar"></span></div>';
    paintRecoDots();
    scheduleRecoCarousel();
  }

  function renderCfmRecommendations(d, abierta) {
    const grid = document.getElementById("ewRecoCards");
    const empty = document.getElementById("ewRecoEmpty");
    const sub = document.getElementById("ewRecoSub");
    const titulo = document.getElementById("ewRecoTitulo");
    const recoIdle = document.getElementById("ewRecoIdle");
    if (!grid) return;

    const rec = d.recomendaciones;
    const items = abierta && rec && Array.isArray(rec.items) ? rec.items : [];
    const identified = clienteIdentificado(d, d.cliente_vitrina);
    const nItems = abierta && Array.isArray(d.lineas) ? d.lineas.length : 0;
    const rk = recoPaintKey(d, abierta);
    const recoSinCambio = rk === lastRecoPaintKey;

    if (recoIdle) {
      recoIdle.classList.toggle("d-none", identified || !abierta || nItems === 0);
    }

    if (titulo) {
      const t =
        rec && rec.titulo ? rec.titulo : "LhexIA IA recomienda para tu proyecto";
      if (titulo.textContent !== t) titulo.textContent = t;
    }

    if (sub) {
      const st =
        rec && rec.subtitulo
          ? rec.subtitulo
          : identified
            ? "Sugerencias según su historial y esta compra"
            : "Sugerencias según lo que lleva en su compra";
      if (sub.textContent !== st) sub.textContent = st;
    }

    if (recoSinCambio) return;

    lastRecoPaintKey = rk;

    if (!items.length) {
      stopRecoCarousel();
      recoCarouselSig = "";
      recoCarouselItems = [];
      grid.innerHTML = "";
      grid.classList.add("d-none");
      grid.classList.remove("ew-cfm-reco-carousel--live");
      if (empty) empty.classList.remove("d-none");
      return;
    }

    if (empty) empty.classList.add("d-none");
    mountRecoCarousel(items);
  }

  function renderValeEmitido(ve) {
    if (!ve || !ve.venta_id) return;
    if (lastValeEmitShown === ve.venta_id) return;
    lastValeEmitShown = ve.venta_id;
    showValeCornerTicket(ve);
  }

  function noteValeEmitido(ve) {
    if (!ve || !ve.venta_id) return;
    renderValeEmitido(ve);
    if (lastThanksValeId === ve.venta_id) return;
    lastThanksValeId = ve.venta_id;
    postEmitVale = ve;
    postThanksSince = Date.now();
    ewPhase = "thanks";
    lastPaintKey = "";
    lastRecoPaintKey = "";
    scheduleThanksToVitrina();
  }

  function clearPostEmitGrace() {
    postEmitVale = null;
    postThanksSince = null;
    if (thanksTimer) {
      clearTimeout(thanksTimer);
      thanksTimer = null;
    }
  }

  function showVitrinaVisual(show) {
    if (!vitrina) return;
    if (show) vitrina.show();
    else vitrina.hide();
  }

  function enterVitrinaMode(payload) {
    const shell = document.getElementById("ewShell");
    const shopping = document.getElementById("ewShopping");
    const thanks = document.getElementById("ewThanks");
    if (shopping) shopping.classList.add("d-none");
    if (thanks) thanks.classList.add("d-none");
    if (shell) shell.classList.add("ew-cfm--vitrina");
    if (payload && vitrina && vitrina.load(payload)) vitrina.show();
  }

  function exitVitrinaMode() {
    const shell = document.getElementById("ewShell");
    vitrinaOnScreen = false;
    if (vitrina) vitrina.hide();
    if (shell) shell.classList.remove("ew-cfm--vitrina");
  }

  function syncVitrinaVisible(va) {
    if (!vitrina) return;
    if (va) vitrina.load(va);
    if (!vitrinaOnScreen && vitrina.hasSlides()) {
      vitrina.show();
      vitrinaOnScreen = true;
    }
  }

  function preloadVitrina(payload) {
    if (payload && vitrina) vitrina.load(payload);
  }

  function paintKeyFromSnap(d, lines, total, abierta) {
    const tv = d.tv_ticket ? Object.assign({}, d.tv_ticket) : defaultTvTicket(d);
    const cv = d.cliente_vitrina || {};
    return [
      abierta ? "abierta" : d.estado,
      d.venta_id || "",
      d.n_lineas != null ? d.n_lineas : (lines || []).length,
      total,
      (lines || []).map((x) => [x.id, x.cantidad, x.subtotal, x.retiro_tag].join(".")).join("|"),
      tv.fecha_hora_txt,
      tv.punto_retiro,
      tv.cliente_nombre || "",
      cv.nombre_publico || "",
      cv.credito_activo ? "1" : "0",
      JSON.stringify(d.recomendaciones || null),
    ].join("~");
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
        const useCfm = document.body.classList.contains("ew-cfm-v2");
        if (useCfm) {
          return (
            '<div class="ew-cfm-line ew-line" data-linea-id="' +
            esc(id) +
            '"><div class="ew-thumb-wrap">' +
            thumb +
            '</div><div><p class="ew-cfm-line__name">' +
            name +
            '</p><span class="ew-cfm-line__meta">' +
            esc(metaBits.join(" · ")) +
            '<span class="ew-cfm-line__qty">× ' +
            esc(String(qty)) +
            "</span></span></div><div class=\"ew-cfm-line__price\">" +
            esc(subtot) +
            "</div></div>"
          );
        }
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
    const cfm = document.body.classList.contains("ew-cfm-v2");
    const cls = cfm ? "ew-cfm-total--glow" : "ew-total-bump";
    el.classList.remove("ew-total-bump", "ew-cfm-total--glow");
    void el.offsetWidth;
    el.classList.add(cls);
    if (cfm) {
      setTimeout(function () {
        el.classList.remove("ew-cfm-total--glow");
      }, 900);
    }
  }

  function snapshotFetchUrl() {
    const sep = snapUrl.indexOf("?") >= 0 ? "&" : "?";
    return snapUrl + sep + "_ts=" + Date.now();
  }

  async function poll() {
    const sub = document.getElementById("ewSub");
    const thanks = document.getElementById("ewThanks");
    const shopping = document.getElementById("ewShopping");
    const itemsEl = document.getElementById("ewItems");
    const totalEl = document.getElementById("ewTotal");
    const shell = document.getElementById("ewShell");
    if (!sub || !itemsEl || !totalEl) return;

    try {
      const r = await fetch(snapshotFetchUrl(), { credentials: "omit", cache: "no-store" });
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
      if (d.vale_emitido) noteValeEmitido(d.vale_emitido);

      const abierta = d.estado === "abierta";
      const sinVenta = d.estado === "sin_venta";
      const lines = abierta ? d.lineas || [] : [];
      const nItems = lines.length;
      const total = abierta ? d.total || 0 : 0;
      const va = vitrinaPayload(d);

      // Vale en vivo con productos → carrito (cancela gracias/vitrina post-emisión).
      if (abierta && nItems > 0) {
        if (d.venta_id && lastThanksValeId && d.venta_id !== lastThanksValeId) {
          lastThanksValeId = null;
        }
        clearPostEmitGrace();
        ewPhase = "cart";
      } else if (ewPhase === "cart") {
        ewPhase = "vitrina";
      } else if (ewPhase === "thanks" && !inThanksPhase()) {
        ewPhase = "vitrina";
      } else if (ewPhase !== "thanks" && ewPhase !== "cart") {
        ewPhase = "vitrina";
      }

      // —— Fase gracias (4 s post-emisión); precarga carrusel detrás ——
      if (ewPhase === "thanks" && inThanksPhase()) {
        if (!thanksVitrinaPaused && vitrina) {
          vitrinaOnScreen = false;
          vitrina.hide();
          thanksVitrinaPaused = true;
        }
        if (shopping) shopping.classList.add("d-none");
        if (shell) shell.classList.remove("ew-cfm--vitrina");
        if (thanks) thanks.classList.remove("d-none");
        if (va && va.activo) preloadVitrina(va);
        sub.textContent =
          d.mensaje_cliente || "Su pedido va a caja para pago. Gracias por su compra.";
        if (totalEl && postEmitVale) totalEl.textContent = fmt(postEmitVale.total || 0);
        const txtThanks = document.getElementById("ewThanksText");
        if (txtThanks) {
          txtThanks.textContent =
            d.mensaje_cliente || "¡Gracias por su compra! Pase a caja para el pago.";
        }
        renderCfmHeader(d, false);
        renderCfmRecommendations(d, false);
        return;
      }

      // —— Fase vitrina: idle, post-gracias, borrador vacío ——
      if (ewPhase === "vitrina") {
        thanksVitrinaPaused = false;
        if (thanks) thanks.classList.add("d-none");
        if (shopping) shopping.classList.add("d-none");
        if (shell) shell.classList.add("ew-cfm--vitrina");
        if (vitrinaReady(d)) {
          syncVitrinaVisible(va);
        } else if (vitrina && vitrina.hasSlides()) {
          syncVitrinaVisible(null);
        } else {
          sub.textContent = vitrinaImgTest
            ? "Modo prueba · cargando imágenes SVG…"
            : "Vitrina digital · cargando catálogo…";
          return;
        }
        if (vitrinaImgTest || (va && va.img_test)) {
          sub.textContent = "Modo prueba · imágenes SVG de diagnóstico";
        } else {
          sub.textContent = "Vitrina digital · Red Chilemat";
        }
        return;
      }

      // —— Carrito en vivo (vale abierto con productos) ——
      exitVitrinaMode();
      if (thanks) thanks.classList.add("d-none");

      renderCfmHeader(d, true);

      if (shell) {
        shell.classList.toggle("ew-cfm--dense", nItems >= 5);
        shell.classList.toggle("ew-shell--dense-lines", nItems >= 4);
        shell.classList.toggle("ew-shell--compact-total", nItems >= 5);
        shell.classList.toggle("ew-shell--mega-dense", nItems >= 7);
      }

      if (shopping) shopping.classList.remove("d-none");
      const cartCount = document.getElementById("ewCartCount");
      const cartEmpty = document.getElementById("ewCartEmpty");
      if (cartCount) {
        cartCount.textContent = nItems === 1 ? "1 producto" : nItems + " productos";
      }
      if (cartEmpty) cartEmpty.classList.toggle("d-none", nItems > 0);

      sub.textContent = "Su compra se actualiza en vivo";

      const pk = paintKeyFromSnap(d, lines, total, true);
      if (pk !== lastPaintKey) {
        lastPaintKey = pk;
        totalEl.textContent = fmt(total);
        bumpTotalEl(totalEl);
        renderLiveProductLines(itemsEl, lines);
      }
      renderCfmRecommendations(d, true);

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
