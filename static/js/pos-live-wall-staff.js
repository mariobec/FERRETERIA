/**
 * Live Wall — monitor vendedor (polling snapshot staff).
 */
(function () {
  "use strict";

  const snapUrl = document.body.getAttribute("data-snapshot-url");
  if (!snapUrl) return;

  const fmt = (n) =>
    new Intl.NumberFormat("es-CL", {
      style: "currency",
      currency: "CLP",
      maximumFractionDigits: 0,
    }).format(Math.round(n || 0));

  const esc = (s) =>
    String(s ?? "")
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/"/g, "&quot;");

  function renderLine(ln) {
    const img = ln.imagen_url
      ? '<img class="lw-thumb" src="' +
        esc(ln.imagen_url) +
        '" alt="" loading="lazy" onerror="this.style.opacity=0.25">'
      : '<div class="lw-thumb lw-thumb-ph"><i class="fas fa-image"></i></div>';
    const stock =
      typeof ln.stock_tienda === "number"
        ? "Tienda " +
          ln.stock_tienda +
          " · Bodega " +
          ln.stock_bodega +
          " · Σ " +
          ln.stock_total_almacenes
        : "";
    const code = ln.codigo_barra ? " · " + esc(ln.codigo_barra) : "";
    return (
      '<div class="lw-line">' +
      img +
      '<div><div class="lw-line-name">' +
      esc(ln.nombre) +
      '</div><div class="lw-line-meta">' +
      ln.cantidad +
      " × " +
      fmt(ln.precio_unitario) +
      (ln.descuento_pct ? " · dto " + ln.descuento_pct + "%" : "") +
      code +
      "</div>" +
      (stock ? '<div class="lw-line-meta">' + stock + "</div>" : "") +
      '</div><div class="lw-line-price">' +
      fmt(ln.subtotal) +
      "</div></div>"
    );
  }

  async function poll() {
    const host = document.getElementById("lwLineas");
    if (!host) return;
    try {
      const r = await fetch(snapUrl, { credentials: "same-origin" });
      const d = await r.json();
      if (!d.ok) {
        host.innerHTML = '<div class="lw-empty">Sin datos de sesión POS.</div>';
        return;
      }
      const k = d.tienda_kpis || {};
      const km = document.getElementById("lwKpiMonto");
      const kd = document.getElementById("lwKpiDocs");
      const kb = document.getElementById("lwKpiBodega");
      if (km) km.textContent = fmt(k.ventas_hoy_monto || 0);
      if (kd) kd.textContent = String(k.ventas_hoy_documentos ?? 0);
      if (kb) kb.textContent = String(k.bodega_retiro_cola ?? 0);

      const est = document.getElementById("lwEstado");
      if (est) est.textContent = (d.estado || "—").toUpperCase();
      const tot = document.getElementById("lwTotal");
      if (tot) tot.textContent = fmt(d.total);

      const lines = d.lineas || [];
      host.innerHTML = lines.length
        ? lines.map(renderLine).join("")
        : '<div class="lw-empty">Carrito vacío. Agregue productos desde el POS.</div>';

      const cli = d.cliente;
      const elCli = document.getElementById("lwCliente");
      if (elCli) {
        elCli.textContent =
          cli && (cli.nombre || cli.rut)
            ? [cli.nombre, cli.rut].filter(Boolean).join(" · ")
            : "Sin cliente en el vale.";
      }
      const sw = document.getElementById("lwSugerenciaWrap");
      if (sw) {
        if (d.sugerencia) {
          sw.classList.remove("d-none");
          sw.textContent = d.sugerencia;
        } else {
          sw.classList.add("d-none");
          sw.textContent = "";
        }
      }
    } catch (e) {
      host.innerHTML = '<div class="lw-empty">Error de red al actualizar.</div>';
    }
  }

  poll();
  setInterval(poll, 4000);

  const copyBtn = document.getElementById("lwCopyBtn");
  if (copyBtn) {
    copyBtn.addEventListener("click", () => {
      const inp = document.getElementById("lwTvUrl");
      if (!inp) return;
      inp.select();
      navigator.clipboard
        .writeText(inp.value)
        .then(() => {
          copyBtn.innerHTML = '<i class="fas fa-check me-1"></i>Copiado';
          setTimeout(() => {
            copyBtn.innerHTML = '<i class="fas fa-copy me-1"></i>Copiar enlace';
          }, 2000);
        })
        .catch(() => {});
    });
  }
})();

