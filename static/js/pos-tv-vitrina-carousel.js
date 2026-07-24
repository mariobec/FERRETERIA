/**
 * Motor carrusel vitrina TV — aislado del polling de venta.
 * Un solo timer por slide; la barra CSS usa la misma duración.
 */
(function (global) {
  "use strict";

  let escenas = [];
  let idx = 0;
  let durMs = 6000;
  let sig = "";
  let slideTimer = null;
  let visible = false;
  let logoUrl = "/static/img/lhexia-icon-hex-login.png";

  let stage = null;
  let slidesEl = null;
  let badgeEl = null;
  let tituloEl = null;
  let subEl = null;
  let dotsEl = null;
  let progressBar = null;

  const fmt = (n) =>
    new Intl.NumberFormat("es-CL", {
      style: "currency",
      currency: "CLP",
      maximumFractionDigits: 0,
    }).format(Math.round(n || 0));

  const fmtPrecio = (n) => {
    const v = Math.round(Number(n) || 0);
    if (v <= 0) return "Consulte en mostrador";
    return fmt(v);
  };

  const esc = (s) =>
    String(s ?? "")
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/"/g, "&quot;");

  function truncName(str, max) {
    const t = String(str || "");
    return t.length <= max ? t : t.slice(0, Math.max(0, max - 1)) + "…";
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

  function vitrinaPremiumStage(url, imgCls, frameCls, alt, variant) {
    const v = variant || "card";
    const inner = vitrinaImg(url, imgCls, alt);
    const pedestal =
      v === "mini" || v === "card"
        ? ""
        : '<div class="ew-vitrina-premium__pedestal" aria-hidden="true"></div>';
    return (
      '<div class="ew-vitrina-premium ew-vitrina-premium--' +
      v +
      '">' +
      '<div class="ew-vitrina-premium__ambient" aria-hidden="true">' +
      '<span class="ew-vitrina-premium__orb ew-vitrina-premium__orb--a"></span>' +
      '<span class="ew-vitrina-premium__orb ew-vitrina-premium__orb--b"></span>' +
      '<span class="ew-vitrina-premium__spot"></span></div>' +
      '<div class="ew-vitrina-premium__stage">' +
      '<div class="ew-vitrina-premium__halo" aria-hidden="true"></div>' +
      '<div class="ew-vitrina-premium__frame">' +
      '<div class="ew-vitrina-premium__ring" aria-hidden="true"></div>' +
      '<div class="' +
      frameCls +
      ' ew-vitrina-premium__img-slot">' +
      inner +
      "</div>" +
      '<div class="ew-vitrina-premium__shine" aria-hidden="true"></div></div>' +
      pedestal +
      "</div></div>"
    );
  }

  function vitrinaImgFrame(url, imgCls, frameCls, alt, variant) {
    return vitrinaPremiumStage(url, imgCls, frameCls, alt, variant || "card");
  }

  function fixVitrinaImages(root) {
    if (!root) return;
    root.querySelectorAll("img.ew-vitrina-hero__img, img.ew-vitrina-card__img, img.ew-vitrina-spot__img, img.ew-vitrina-mini__img").forEach(function (img) {
      var apply = function () {
        img.style.removeProperty("width");
        img.style.removeProperty("height");
        img.style.maxWidth = "100%";
        img.style.maxHeight = "100%";
        img.style.objectFit = "contain";
        img.style.objectPosition = "center center";
      };
      if (img.complete) apply();
      else img.addEventListener("load", apply, { once: true });
    });
  }

  function vitrinaImg(url, cls, alt) {
    const u = String(url || "").trim();
    if (u) {
      return (
        '<img class="' +
        cls +
        '" src="' +
        esc(u) +
        '" alt="' +
        esc(alt || "") +
        '" loading="eager" decoding="async" referrerpolicy="no-referrer" />'
      );
    }
    return (
      '<div class="' +
      cls +
      ' ew-vitrina-ph" aria-hidden="true"><i class="fas fa-screwdriver-wrench"></i></div>'
    );
  }

  function initDom() {
    stage = document.getElementById("ewVitrinaStage");
    slidesEl = document.getElementById("ewVitrinaSlides");
    badgeEl = document.getElementById("ewVitrinaBadge");
    tituloEl = document.getElementById("ewVitrinaTitulo");
    subEl = document.getElementById("ewVitrinaSub");
    dotsEl = document.getElementById("ewVitrinaDots");
    progressBar = document.getElementById("ewVitrinaProgressBar");
  }

  function payloadSig(payload) {
    if (!payload || !payload.escenas) return "";
    return [
      payload.n_escenas || (payload.escenas || []).length,
      payload.duracion_seg || 6,
      (payload.escenas || [])
        .map(function (s) {
          const heroId = s.hero && s.hero.id != null ? s.hero.id : "";
          const firstItemId =
            s.items && s.items[0] && s.items[0].id != null ? s.items[0].id : "";
          return [s.tipo || "", s.titulo || "", heroId, firstItemId, (s.items || []).length].join(":");
        })
        .join("|"),
    ].join("~");
  }

  function renderProyectoChilemat(escena) {
    const h = escena.hero;
    if (!h) return "";
    const comps = (escena.complementos || [])
      .slice(0, 3)
      .map(function (c, i) {
        return (
          '<article class="ew-vitrina-mini ew-vitrina-mini--in" style="--ew-stagger:' +
          i +
          '">' +
          '<div class="ew-vitrina-mini__media">' +
          vitrinaPremiumStage(
            c.imagen_url,
            "ew-vitrina-mini__img",
            "ew-vitrina-mini__img-frame",
            c.nombre,
            "mini"
          ) +
          "</div>" +
          '<div><p class="ew-vitrina-mini__name">' +
          esc(truncName(c.nombre, 56)) +
          '</p><p class="ew-vitrina-mini__motivo">' +
          esc(shortMotivo(c.motivo, 72)) +
          '</p><p class="ew-vitrina-mini__price">' +
          esc(fmtPrecio(c.precio || 0)) +
          "</p></div></article>"
        );
      })
      .join("");
    return (
      '<div class="ew-vitrina-hero ew-vitrina-hero--live">' +
      '<div class="ew-vitrina-hero__main ew-vitrina-hero__main--in">' +
      '<div class="ew-vitrina-hero__img-wrap">' +
      vitrinaImgFrame(
        h.imagen_url,
        "ew-vitrina-hero__img",
        "ew-vitrina-hero__img-frame",
        h.nombre,
        "hero"
      ) +
      "</div>" +
      '<div class="ew-vitrina-hero__info"><p class="ew-vitrina-hero__name">' +
      esc(truncName(h.nombre, 72)) +
      '</p><p class="ew-vitrina-hero__price ew-vitrina-price--pulse">' +
      esc(fmtPrecio(h.precio || 0)) +
      "</p></div></div>" +
      '<div class="ew-vitrina-hero__side">' +
      comps +
      "</div></div>"
    );
  }

  function renderProductoDestacado(escena) {
    const h = escena.hero;
    if (!h) return "";
    const motivo = shortMotivo(h.motivo || h.categoria || "", 80);
    const motivoHtml = motivo ? '<p class="ew-vitrina-spot__motivo">' + esc(motivo) + "</p>" : "";
    return (
      '<div class="ew-vitrina-spot">' +
      '<div class="ew-vitrina-spot__media">' +
      vitrinaImgFrame(
        h.imagen_url,
        "ew-vitrina-spot__img",
        "ew-vitrina-spot__img-frame",
        h.nombre,
        "spot"
      ) +
      "</div>" +
      '<div class="ew-vitrina-spot__info">' +
      '<p class="ew-vitrina-spot__name">' +
      esc(truncName(h.nombre, 80)) +
      "</p>" +
      motivoHtml +
      '<p class="ew-vitrina-spot__price">' +
      esc(fmtPrecio(h.precio || 0)) +
      "</p></div></div>"
    );
  }

  function renderGridDestacados(escena) {
    const maxItems = Math.min(6, parseInt(String(escena.max_items || 6), 10) || 6);
    const items = (escena.items || []).slice(0, maxItems);
    if (!items.length) return "";
    const dense = items.length >= 7 ? " ew-vitrina-grid--dense" : " ew-vitrina-grid--6";
    return (
      '<div class="ew-vitrina-grid' +
      dense +
      '">' +
      items
        .map(function (it, i) {
          const motivo = shortMotivo(it.motivo || it.categoria || "", 48);
          const motivoHtml = motivo
            ? '<p class="ew-vitrina-card__motivo">' + esc(motivo) + "</p>"
            : "";
          return (
            '<article class="ew-vitrina-card ew-vitrina-card--in" style="--ew-stagger:' +
            i +
            '">' +
            '<div class="ew-vitrina-card__shine" aria-hidden="true"></div>' +
            '<div class="ew-vitrina-card__media">' +
            vitrinaImgFrame(
              it.imagen_url,
              "ew-vitrina-card__img",
              "ew-vitrina-card__img-frame",
              it.nombre,
              "card"
            ) +
            "</div>" +
            '<div class="ew-vitrina-card__body"><p class="ew-vitrina-card__name">' +
            esc(truncName(it.nombre, 52)) +
            "</p>" +
            motivoHtml +
            '<p class="ew-vitrina-card__price">' +
            esc(fmtPrecio(it.precio || 0)) +
            "</p></div></article>"
          );
        })
        .join("") +
      "</div>"
    );
  }

  function renderMarcaLocal(escena) {
    const bullets = (escena.bullets || [])
      .map(function (b, i) {
        return (
          '<li class="ew-vitrina-marca__li--in" style="--ew-stagger:' +
          i +
          '"><i class="fas fa-check"></i>' +
          esc(b) +
          "</li>"
        );
      })
      .join("");
    const link = escena.catalogo_url
      ? '<a class="ew-vitrina-marca__link ew-vitrina-marca__link--in" href="' +
        esc(escena.catalogo_url) +
        '" target="_blank" rel="noopener"><i class="fas fa-qrcode"></i> Ver catálogo en línea</a>'
      : "";
    return (
      '<div class="ew-vitrina-marca ew-vitrina-marca--in">' +
      '<img class="ew-vitrina-marca__logo ew-vitrina-marca__logo--float" src="' +
      esc(logoUrl) +
      '" alt="" />' +
      "<ul class=\"ew-vitrina-marca__bullets\">" +
      bullets +
      "</ul>" +
      link +
      "</div>"
    );
  }

  function renderPromoCampana(escena) {
    const layout = String(escena.layout || "flyer");
    const img = esc(escena.imagen_url || "");
    const oferta = esc(escena.oferta || "");
    const prod = esc(escena.producto_nombre || escena.titulo || "");
    const cta = esc(escena.cta || "Consulte en mostrador");
    if (layout === "producto") {
      return (
        '<div class="ew-vitrina-promo ew-vitrina-promo--producto">' +
        '<div class="ew-vitrina-promo__copy">' +
        '<p class="ew-vitrina-promo__kicker">¡Súper oferta!</p>' +
        '<h3 class="ew-vitrina-promo__name">' +
        prod +
        "</h3>" +
        '<p class="ew-vitrina-promo__deal">' +
        oferta +
        "</p>" +
        '<p class="ew-vitrina-promo__cta">' +
        cta +
        "</p></div>" +
        '<div class="ew-vitrina-promo__media">' +
        (img
          ? '<img class="ew-vitrina-promo__img" src="' + img + '" alt="' + prod + '" loading="eager">'
          : "") +
        "</div></div>"
      );
    }
    return (
      '<div class="ew-vitrina-promo ew-vitrina-promo--flyer">' +
      (img
        ? '<img class="ew-vitrina-promo__flyer" src="' + img + '" alt="' + esc(escena.titulo || "Promoción") + '" loading="eager">'
        : '<div class="ew-vitrina-promo__fallback"><p class="ew-vitrina-promo__deal">' +
          oferta +
          "</p></div>") +
      "</div>"
    );
  }

  function renderSlideBody(escena) {
    const tipo = escena.tipo || "";
    if (tipo === "promo_campana") return renderPromoCampana(escena);
    if (tipo === "proyecto_chilemat") return renderProyectoChilemat(escena);
    if (tipo === "producto_destacado") return renderProductoDestacado(escena);
    if (tipo === "grid_destacados") return renderGridDestacados(escena);
    if (tipo === "marca_local") return renderMarcaLocal(escena);
    return "";
  }

  function paintDots() {
    if (!dotsEl) return;
    const dots = dotsEl.querySelectorAll("span");
    for (let i = 0; i < escenas.length; i++) {
      if (dots[i]) {
        dots[i].classList.toggle("is-active", i === idx);
      }
    }
    if (dots.length === escenas.length) return;
    let html = "";
    for (let i = 0; i < escenas.length; i++) {
      html += '<span class="' + (i === idx ? "is-active" : "") + '" aria-hidden="true"></span>';
    }
    dotsEl.innerHTML = html;
  }

  function armProgressBar() {
    if (!progressBar) return;
    progressBar.style.setProperty("--ew-progress-dur", durMs + "ms");
    progressBar.classList.remove("is-running");
    void progressBar.offsetWidth;
    progressBar.classList.add("is-running");
  }

  function updateChrome(i) {
    const e = escenas[i];
    if (!e) return;
    if (badgeEl) badgeEl.textContent = e.badge || "Red Chilemat";
    if (tituloEl) tituloEl.textContent = e.titulo || "Bienvenido";
    if (subEl) subEl.textContent = e.subtitulo || "";
  }

  function applySlide(nextIdx, opts) {
    opts = opts || {};
    initDom();
    if (!escenas.length || !slidesEl) return;
    idx = ((nextIdx % escenas.length) + escenas.length) % escenas.length;
    const slides = slidesEl.querySelectorAll(".ew-vitrina-slide");
    for (let i = 0; i < slides.length; i++) {
      slides[i].classList.toggle("is-active", i === idx);
    }
    updateChrome(idx);
    paintDots();
    if (opts.armProgress !== false && visible) armProgressBar();
  }

  function stopAutoplay() {
    if (slideTimer !== null) {
      clearTimeout(slideTimer);
      slideTimer = null;
    }
  }

  function scheduleAdvance() {
    stopAutoplay();
    if (!visible || escenas.length <= 1) return;
    armProgressBar();
    slideTimer = global.setTimeout(function () {
      slideTimer = null;
      applySlide(idx + 1, { armProgress: false });
      scheduleAdvance();
    }, durMs);
  }

  function mountSlides(list) {
    initDom();
    if (!slidesEl) return;
    escenas = list.slice();
    slidesEl.innerHTML = escenas
      .map(function (e, i) {
        return (
          '<div class="ew-vitrina-slide' +
          (i === 0 ? " is-active" : "") +
          '" data-slide="' +
          i +
          '">' +
          renderSlideBody(e) +
          "</div>"
        );
      })
      .join("");
    applySlide(0, { armProgress: false });
    fixVitrinaImages(slidesEl);
    if (visible) scheduleAdvance();
  }

  function load(payload) {
    initDom();
    if (!slidesEl || !payload || !payload.activo || !payload.escenas || !payload.escenas.length) {
      return false;
    }
    const sec = Math.max(4, Math.min(30, parseInt(String(payload.duracion_seg || 6), 10) || 6));
    durMs = sec * 1000;
    const newSig = payloadSig(payload);
    if (newSig === sig && escenas.length) {
      return true;
    }
    sig = newSig;
    mountSlides(payload.escenas);
    return true;
  }

  function show() {
    initDom();
    visible = true;
    if (stage) stage.classList.remove("d-none");
    if (escenas.length && slideTimer === null) scheduleAdvance();
  }

  function hide() {
    if (!visible) return;
    visible = false;
    stopAutoplay();
    if (progressBar) progressBar.classList.remove("is-running");
    if (stage) stage.classList.add("d-none");
  }

  function destroy() {
    hide();
    sig = "";
    escenas = [];
    idx = 0;
    if (slidesEl) slidesEl.innerHTML = "";
  }

  function hasSlides() {
    return escenas.length > 0;
  }

  function setLogoUrl(url) {
    if (url) logoUrl = url;
  }

  global.EwVitrinaCarousel = {
    load: load,
    show: show,
    hide: hide,
    destroy: destroy,
    hasSlides: hasSlides,
    setLogoUrl: setLogoUrl,
  };
})(window);
