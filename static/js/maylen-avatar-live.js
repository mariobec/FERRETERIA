/**
 * Maylén — animación en el contenedor (idle + saludo al abrir).
 */
(function () {
  "use strict";

  function playWave(el) {
    if (!el) return;
    el.classList.remove("is-waving");
    void el.offsetWidth;
    el.classList.add("is-waving");
    window.setTimeout(function () {
      el.classList.remove("is-waving");
    }, 1500);
  }

  function waveAll() {
    document.querySelectorAll(".maylen-avatar-live").forEach(playWave);
  }

  function init() {
    var toggle = document.getElementById("tiendaAssistantToggle");
    var panel = document.getElementById("tiendaAssistantPanel");

    document.querySelectorAll(".maylen-avatar-live").forEach(function (el) {
      el.classList.add("maylen-avatar-live--idle");
    });

    window.playMaylenWave = waveAll;

    if (toggle && panel) {
      toggle.addEventListener("click", function () {
        if (panel.classList.contains("d-none")) {
          window.setTimeout(waveAll, 100);
        }
      });
    }
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
