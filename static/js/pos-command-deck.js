/**
 * LhexIA Command Deck — fullscreen, atajos y KPIs vía Live Wall snapshot.
 */
(function () {
  "use strict";

  function readDeckConfig() {
    const el = document.getElementById("deck-config");
    if (!el) return {};
    try {
      return JSON.parse(el.textContent || "{}");
    } catch (e) {
      return {};
    }
  }

  function fmtMonto(n) {
    const v = Math.round(Number(n) || 0);
    return "$" + v.toLocaleString("es-CL");
  }

  function toggleFullscreen() {
    const root = document.documentElement;
    if (!document.fullscreenElement) {
      root.requestFullscreen?.().catch(function () {});
    } else {
      document.exitFullscreen?.();
    }
  }

  function bindFullscreen() {
    const btn = document.getElementById("deckBtnFullscreen");
    if (btn) {
      btn.addEventListener("click", toggleFullscreen);
    }
    document.addEventListener("keydown", function (e) {
      if (e.key === "F11") {
        e.preventDefault();
        toggleFullscreen();
      }
    });
    document.addEventListener("fullscreenchange", function () {
      if (!btn) return;
      const icon = btn.querySelector("i");
      if (!icon) return;
      icon.className = document.fullscreenElement
        ? "fas fa-compress"
        : "fas fa-expand";
    });
  }

  function bindClienteRutQuick() {
    const quick = document.getElementById("deckClienteRutQuick");
    const hidden = document.getElementById("cliente_rut");
    const buscarBtn = document.getElementById("buscarClienteBtn");
    if (!quick || !hidden) return;

    function sync() {
      hidden.value = (quick.value || "").trim();
    }

    quick.addEventListener("input", sync);
    quick.addEventListener("change", sync);
    if (hidden.value) {
      quick.value = hidden.value;
    }
    // Enter / auto-búsqueda RUT: cubierto en pos.js para #deckClienteRutQuick (Command Deck) y #posIdentRutQuick (POS clásico).
    if (buscarBtn) {
      buscarBtn.addEventListener("click", sync);
    }
  }

  function bindKpiPolling(cfg) {
    const url = cfg.snapshot_url;
    if (!url) return;

    const kpis = document.querySelectorAll(".deck-kpi strong");
    if (kpis.length < 3) return;

    function apply(data) {
      if (!data || !data.ok) return;
      const tk = data.tienda_kpis;
      if (tk && typeof tk.ventas_hoy_monto === "number") {
        kpis[2].textContent = fmtMonto(tk.ventas_hoy_monto);
      }
      const total = data.total;
      if (typeof total === "number" && document.getElementById("monto_total")) {
        const mt = document.getElementById("monto_total");
        const mc = document.getElementById("monto_total_cockpit");
        const txt = String(Math.round(total));
        if (mt.textContent !== txt) {
          mt.textContent = txt;
          if (mc) mc.textContent = txt;
        }
      }
    }

    function poll() {
      fetch(url, { credentials: "same-origin", headers: { Accept: "application/json" } })
        .then(function (r) {
          return r.ok ? r.json() : null;
        })
        .then(apply)
        .catch(function () {});
    }

    poll();
    setInterval(poll, 12000);
  }

  document.addEventListener("DOMContentLoaded", function () {
    bindFullscreen();
    bindClienteRutQuick();
    bindKpiPolling(readDeckConfig());
    const wedge = document.getElementById("posBarcodeWedge");
    if (wedge) {
      setTimeout(function () {
        wedge.focus();
      }, 200);
    }
  });
})();
