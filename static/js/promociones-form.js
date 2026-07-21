(function () {
  "use strict";

  var root = document.getElementById("promoSearchRoot");
  var input = document.getElementById("promoSearchInput");
  var resultsEl = document.getElementById("promoSearchResults");
  var chipsEl = document.getElementById("promoChips");
  var chipsEmpty = document.getElementById("promoChipsEmpty");
  var chipsError = document.getElementById("promoChipsError");
  var hiddenIds = document.getElementById("promoProductoIds");
  var form = document.getElementById("promoForm");
  var tipoSel = document.getElementById("promoTipo");
  if (!root || !input || !chipsEl || !hiddenIds) return;

  var urlBuscar = root.getAttribute("data-url") || "";
  var selected = {};
  var debounceTimer = null;
  var activeIdx = -1;
  var lastResults = [];

  chipsEl.querySelectorAll(".promo-chip").forEach(function (chip) {
    var id = parseInt(chip.getAttribute("data-id"), 10);
    if (!id) return;
    var nameEl = chip.querySelector(".promo-chip__name");
    var metaEl = chip.querySelector(".promo-chip__meta");
    selected[id] = {
      id: id,
      nombre: (nameEl && nameEl.textContent) || ("#" + id),
      meta: (metaEl && metaEl.textContent) || "",
    };
  });
  syncHidden();

  function esc(s) {
    var d = document.createElement("div");
    d.textContent = s == null ? "" : String(s);
    return d.innerHTML;
  }

  function syncHidden() {
    var ids = Object.keys(selected)
      .map(function (k) {
        return parseInt(k, 10);
      })
      .filter(function (n) {
        return n > 0;
      })
      .sort(function (a, b) {
        return a - b;
      });
    hiddenIds.value = ids.join(",");
    if (chipsEmpty) chipsEmpty.classList.toggle("d-none", ids.length > 0);
    if (chipsError && ids.length > 0) chipsError.classList.add("d-none");
  }

  function renderChips() {
    var html = "";
    Object.keys(selected)
      .map(function (k) {
        return parseInt(k, 10);
      })
      .sort(function (a, b) {
        return a - b;
      })
      .forEach(function (id) {
        var p = selected[id];
        html +=
          '<div class="promo-chip" data-id="' +
          id +
          '">' +
          '<div class="promo-chip__body">' +
          '<strong class="promo-chip__name">' +
          esc(p.nombre) +
          "</strong>" +
          '<span class="promo-chip__meta">' +
          esc(p.meta || "#" + id) +
          "</span>" +
          "</div>" +
          '<button type="button" class="promo-chip__remove" data-remove="' +
          id +
          '" title="Quitar" aria-label="Quitar">&times;</button>' +
          "</div>";
      });
    chipsEl.innerHTML = html;
    syncHidden();
  }

  function addProduct(item) {
    var id = parseInt(item.id || item.producto_id, 10);
    if (!id) return;
    if (selected[id]) {
      input.value = "";
      hideResults();
      return;
    }
    var metaParts = ["#" + id];
    if (item.codigo) metaParts.push(item.codigo);
    if (item.precio_fmt) metaParts.push(item.precio_fmt);
    selected[id] = {
      id: id,
      nombre: item.nombre || "Producto #" + id,
      meta: metaParts.join(" · "),
    };
    renderChips();
    input.value = "";
    hideResults();
    input.focus();
  }

  function removeProduct(id) {
    delete selected[id];
    renderChips();
  }

  function hideResults() {
    resultsEl.classList.add("d-none");
    resultsEl.innerHTML = "";
    activeIdx = -1;
    lastResults = [];
  }

  function showLoading() {
    resultsEl.classList.remove("d-none");
    resultsEl.innerHTML = '<div class="promo-search__loading">Buscando…</div>';
  }

  function renderResults(rows) {
    lastResults = rows || [];
    activeIdx = lastResults.length ? 0 : -1;
    if (!lastResults.length) {
      resultsEl.classList.remove("d-none");
      resultsEl.innerHTML =
        '<div class="promo-search__empty">Sin coincidencias. Prueba nombre o código de barras.</div>';
      return;
    }
    var html = "";
    lastResults.forEach(function (r, i) {
      var id = parseInt(r.id || r.producto_id, 10);
      var already = !!selected[id];
      html +=
        '<button type="button" class="promo-search__item' +
        (i === 0 ? " is-active" : "") +
        '" role="option" data-idx="' +
        i +
        '"' +
        (already ? ' disabled title="Ya agregado"' : "") +
        ">" +
        "<span>" +
        '<span class="promo-search__item-name">' +
        esc(r.nombre || "") +
        (already ? " · ya agregado" : "") +
        "</span>" +
        '<span class="promo-search__item-meta">#' +
        id +
        (r.codigo ? " · " + esc(r.codigo) : "") +
        (r.stock_tienda != null ? " · Stock T " + esc(r.stock_tienda) : "") +
        "</span>" +
        "</span>" +
        '<span class="promo-search__item-price">' +
        esc(r.precio_fmt || "") +
        "</span>" +
        "</button>";
    });
    resultsEl.classList.remove("d-none");
    resultsEl.innerHTML = html;
  }

  function markActive() {
    var items = resultsEl.querySelectorAll(".promo-search__item");
    items.forEach(function (el, i) {
      el.classList.toggle("is-active", i === activeIdx);
    });
    if (activeIdx >= 0 && items[activeIdx]) {
      items[activeIdx].scrollIntoView({ block: "nearest" });
    }
  }

  function buscar(q) {
    q = (q || "").trim();
    if (q.length < 1) {
      hideResults();
      return;
    }
    if (!urlBuscar) return;
    showLoading();
    fetch(urlBuscar + "?q=" + encodeURIComponent(q), {
      credentials: "same-origin",
      headers: { Accept: "application/json" },
    })
      .then(function (res) {
        return res.json().catch(function () {
          return {};
        });
      })
      .then(function (data) {
        if ((input.value || "").trim() !== q) return;
        renderResults(data.results || []);
      })
      .catch(function () {
        resultsEl.classList.remove("d-none");
        resultsEl.innerHTML =
          '<div class="promo-search__empty">Error de búsqueda. Revisa la conexión.</div>';
      });
  }

  input.addEventListener("input", function () {
    clearTimeout(debounceTimer);
    var q = input.value;
    debounceTimer = setTimeout(function () {
      buscar(q);
    }, 220);
  });

  input.addEventListener("keydown", function (ev) {
    if (ev.key === "ArrowDown") {
      if (!lastResults.length) return;
      ev.preventDefault();
      activeIdx = Math.min(activeIdx + 1, lastResults.length - 1);
      markActive();
    } else if (ev.key === "ArrowUp") {
      if (!lastResults.length) return;
      ev.preventDefault();
      activeIdx = Math.max(activeIdx - 1, 0);
      markActive();
    } else if (ev.key === "Enter") {
      ev.preventDefault();
      if (activeIdx >= 0 && lastResults[activeIdx]) {
        addProduct(lastResults[activeIdx]);
      } else {
        buscar(input.value);
      }
    } else if (ev.key === "Escape") {
      hideResults();
    }
  });

  resultsEl.addEventListener("mousedown", function (ev) {
    var btn = ev.target.closest(".promo-search__item");
    if (!btn || btn.disabled) return;
    ev.preventDefault();
    var idx = parseInt(btn.getAttribute("data-idx"), 10);
    if (!isNaN(idx) && lastResults[idx]) addProduct(lastResults[idx]);
  });

  chipsEl.addEventListener("click", function (ev) {
    var btn = ev.target.closest("[data-remove]");
    if (!btn) return;
    var id = parseInt(btn.getAttribute("data-remove"), 10);
    if (id) removeProduct(id);
  });

  document.addEventListener("click", function (ev) {
    if (!root.contains(ev.target)) hideResults();
  });

  if (form) {
    form.addEventListener("submit", function (ev) {
      syncHidden();
      if (codigoEditable && manualBox && !manualBox.classList.contains("d-none")) {
        var manualVal = (codigoEditable.value || "").trim().toUpperCase();
        if (manualVal && codigoInput) codigoInput.value = manualVal;
      }
      var ids = (hiddenIds.value || "").trim();
      if (!ids) {
        ev.preventDefault();
        if (chipsError) chipsError.classList.remove("d-none");
        input.focus();
        return;
      }
    });
  }

  if (tipoSel) {
    function syncTipo() {
      var t = (tipoSel.value || "").toUpperCase();
      var nxm = document.getElementById("blkNxm");
      var par = document.getElementById("blkPrecioPar");
      var seg = document.getElementById("blkSegundo");
      var esc = document.getElementById("blkEscala");
      if (nxm) nxm.classList.toggle("d-none", t !== "NXM");
      if (par) par.classList.toggle("d-none", t !== "PRECIO_PAR");
      if (seg) seg.classList.toggle("d-none", t !== "SEGUNDO_PCT");
      if (esc) esc.classList.toggle("d-none", t !== "ESCALA_QTY");
    }
    tipoSel.addEventListener("change", syncTipo);
    syncTipo();
  }

  /* Código interno auto + preview */
  var codigoInput = document.getElementById("promoCodigo");
  var codigoEditable = document.getElementById("promoCodigoEditable");
  var codigoPreview = document.getElementById("promoCodigoPreview");
  var nombreInput = document.getElementById("promoNombre");
  var btnGen = document.getElementById("promoBtnGenerarCodigo");
  var btnToggle = document.getElementById("promoCodigoToggle");
  var manualBox = document.getElementById("promoCodigoManual");
  var urlSugerir = (form && form.getAttribute("data-url-sugerir")) || "";
  var promoId = (form && form.getAttribute("data-promo-id")) || "";
  var autoMode = (form && form.getAttribute("data-auto-codigo") || "1") === "1";
  var codigoManual = !autoMode;

  function setCodigoVisible(val) {
    var v = (val || "").trim();
    if (codigoInput) codigoInput.value = v;
    if (codigoEditable && document.activeElement !== codigoEditable) {
      codigoEditable.value = v;
    }
    if (codigoPreview) {
      codigoPreview.textContent = v || "Se creará al escribir el nombre…";
    }
  }

  if (codigoEditable) {
    codigoEditable.addEventListener("input", function () {
      codigoManual = !!(codigoEditable.value || "").trim();
      if (codigoInput) codigoInput.value = (codigoEditable.value || "").trim().toUpperCase();
      if (codigoPreview) {
        codigoPreview.textContent = codigoInput.value || "Se creará al escribir el nombre…";
      }
    });
  }

  if (btnToggle && manualBox) {
    btnToggle.addEventListener("click", function () {
      manualBox.classList.toggle("d-none");
      if (!manualBox.classList.contains("d-none") && codigoEditable) {
        codigoEditable.focus();
      }
    });
  }

  function leerBeneficioParams() {
    var nEl = document.querySelector('input[name="nxm_n"]');
    var mEl = document.querySelector('input[name="nxm_m"]');
    var pEl = document.querySelector('input[name="segundo_pct"]');
    var pqEl = document.querySelector('input[name="par_qty"]');
    var ppEl = document.querySelector('input[name="par_precio"]');
    return {
      n: (nEl && nEl.value) || "2",
      m: (mEl && mEl.value) || "1",
      pct: (pEl && pEl.value) || "50",
      pack_qty: (pqEl && pqEl.value) || "2",
      precio_pack: (ppEl && ppEl.value) || "0",
    };
  }

  function sugerirCodigo(force) {
    if (!urlSugerir || !codigoInput) return;
    if (!force && codigoManual) return;
    var tipo = (tipoSel && tipoSel.value) || "NXM";
    var nombre = (nombreInput && nombreInput.value) || "";
    var b = leerBeneficioParams();
    var qs =
      "?tipo=" +
      encodeURIComponent(tipo) +
      "&nombre=" +
      encodeURIComponent(nombre) +
      "&n=" +
      encodeURIComponent(b.n) +
      "&m=" +
      encodeURIComponent(b.m) +
      "&pct=" +
      encodeURIComponent(b.pct) +
      "&pack_qty=" +
      encodeURIComponent(b.pack_qty) +
      "&precio_pack=" +
      encodeURIComponent(b.precio_pack);
    if (promoId) qs += "&excluir_id=" + encodeURIComponent(promoId);
    fetch(urlSugerir + qs, {
      credentials: "same-origin",
      headers: { Accept: "application/json" },
    })
      .then(function (r) {
        return r.json().catch(function () {
          return {};
        });
      })
      .then(function (data) {
        if (!data || !data.ok || !data.codigo) return;
        if (!force && codigoManual) return;
        setCodigoVisible(data.codigo);
        if (force) codigoManual = false;
      })
      .catch(function () {});
  }

  if (btnGen) {
    btnGen.addEventListener("click", function () {
      codigoManual = false;
      sugerirCodigo(true);
    });
  }
  var sugerirTimer = null;
  function scheduleSugerir() {
    clearTimeout(sugerirTimer);
    sugerirTimer = setTimeout(function () {
      sugerirCodigo(false);
    }, 350);
  }
  if (nombreInput) nombreInput.addEventListener("input", scheduleSugerir);
  if (tipoSel) tipoSel.addEventListener("change", scheduleSugerir);
  document.querySelectorAll(
    'input[name="nxm_n"], input[name="nxm_m"], input[name="segundo_pct"], input[name="par_qty"], input[name="par_precio"]'
  ).forEach(function (el) {
    el.addEventListener("input", scheduleSugerir);
  });
  if (!codigoManual) {
    sugerirCodigo(false);
  } else {
    setCodigoVisible(codigoInput.value);
  }

  /* Popovers de ayuda (?) */
  if (window.bootstrap && bootstrap.Popover) {
    document.querySelectorAll('.promo-help[data-bs-toggle="popover"]').forEach(function (el) {
      if (!bootstrap.Popover.getInstance(el)) {
        new bootstrap.Popover(el, { container: "body" });
      }
    });
  }
})();
