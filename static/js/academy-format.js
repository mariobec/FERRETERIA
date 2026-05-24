/**
 * LhexIA Academy — formateo HUD (badges, callouts, atajos).
 */
(function (global) {
  "use strict";

  var INVARIANTE_FINANCIERA =
    "Invariante Financiera: El POS jamás recauda dinero real; el flujo operativo se cierra única y exclusivamente en la estación de Caja.";

  var BADGE_VERDE =
    '<span class="badge bg-success-subtle text-success border border-success-subtle px-2 py-1">' +
    '<i class="fas fa-circle me-1" style="font-size:0.5rem;"></i> Entrega Inmediata</span>';
  var BADGE_AMARILLO =
    '<span class="badge bg-warning-subtle text-warning border border-warning-subtle px-2 py-1">' +
    '<i class="fas fa-circle me-1" style="font-size:0.5rem;"></i> Reserva Parcial</span>';
  var BADGE_NARANJA =
    '<span class="badge text-orange border px-2 py-1" style="color:#ff5500;border-color:#ff5500;background:rgba(255,85,0,0.12);font-weight:600;">' +
    '<i class="fas fa-bolt me-1"></i> Venta en Verde</span>';

  function escapeHtml(value) {
    return String(value == null ? "" : value)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  function normalizarAtajosTexto(texto) {
    if (!texto) return "";
    var out = String(texto);
    out = out.replace(/`?F8`?\s*(?:→|->|:)?\s*(?:Foco\s+b[uú]squeda|buscar|enfocar|foco)[^.\n|]*/gi,
      "F2 → Foco búsqueda de producto / Invocación de Escáner universal");
    out = out.replace(/`?F9`?\s*(?:→|->|:)?\s*(?:Emitir\s+vale|emitir)[^.\n|]*/gi,
      "F8 → Emitir vale de venta pendiente (Bloqueo de caja diferido)");
    out = out.replace(/`?F2`?\s*(?:→|->|:)?\s*(?:Foco|buscar|b[uú]squeda)[^.\n|]*/gi,
      "F2 → Foco búsqueda de producto / Invocación de Escáner universal");
    out = out.replace(/`?Esc`?\s*(?:→|->|:)?\s*[^.\n|]*/gi,
      "Esc → Cerrar modal o cancelar línea actual");
    return out;
  }

  function aplicarBadgesLinea(lineaEsc) {
    var linea = lineaEsc;
    linea = linea.replace(/\*\*Verde:\*\*|\*\*Verde\*\*|🟢\s*Verde/gi, BADGE_VERDE);
    linea = linea.replace(/\*\*Amarillo:\*\*|\*\*Amarillo\*\*|🟡\s*Amarillo/gi, BADGE_AMARILLO);
    linea = linea.replace(/\*\*Rojo:\*\*|\*\*Rojo\*\*|\*\*Naranja:\*\*|\*\*Naranja\*\*|🍊\s*Naranja|🔴\s*Rojo/gi, BADGE_NARANJA);
    return linea;
  }

  function formatAcademyRichText(texto) {
    if (!texto) return "";
    texto = normalizarAtajosTexto(texto);
    var bloques = [];
    var listaItems = [];
    var listaTipo = "ul";

    function flushLista() {
      if (!listaItems.length) return;
      var items = listaItems.map(function (i) { return "<li>" + i + "</li>"; }).join("");
      bloques.push("<" + listaTipo + ' class="lhexia-academy-list">' + items + "</" + listaTipo + ">");
      listaItems = [];
    }

    texto.split("\n").forEach(function (raw) {
      var stripped = (raw || "").trim();
      if (!stripped) {
        flushLista();
        return;
      }
      if (stripped.indexOf("|") >= 0 && stripped.charAt(0) === "|") {
        flushLista();
        var celdas = stripped.replace(/^\|/, "").replace(/\|$/, "").split("|").map(function (c) { return c.trim(); });
        if (celdas.length >= 2 && celdas[0].toLowerCase() !== "tecla" && celdas[0].indexOf("---") < 0) {
          bloques.push(
            '<div class="lhexia-academy-kbd-row"><kbd>' +
            escapeHtml(normalizarAtajosTexto(celdas[0])) +
            "</kbd><span>" +
            escapeHtml(normalizarAtajosTexto(celdas[1])) +
            "</span></div>"
          );
        }
        return;
      }
      if (/^[-|:\s]+$/.test(stripped)) return;
      if (stripped.indexOf("> ") === 0) {
        flushLista();
        bloques.push('<div class="lhexia-academy-callout">' + escapeHtml(stripped.slice(2).trim()) + "</div>");
        return;
      }
      if (/^Importante\s*:/i.test(stripped)) {
        flushLista();
        bloques.push(
          '<div class="lhexia-academy-callout">' +
          escapeHtml(stripped.replace(/^Importante\s*:\s*/i, "")) +
          "</div>"
        );
        return;
      }
      var mHead = stripped.match(/^#{1,3}\s+(.+)$/);
      if (mHead) {
        flushLista();
        bloques.push('<div class="lhexia-academy-subtitle">' + escapeHtml(mHead[1]) + "</div>");
        return;
      }
      if (/^📌\s*PROTOCOLO/i.test(stripped) || /^Sección\s+\d/i.test(stripped)) {
        flushLista();
        bloques.push('<div class="lhexia-academy-subtitle">' + escapeHtml(stripped) + "</div>");
        return;
      }
      var mNum = stripped.match(/^\d+[\.\)]\s*(.+)$/);
      if (mNum) {
        if (listaTipo !== "ol") { flushLista(); listaTipo = "ol"; }
        listaItems.push(aplicarBadgesLinea(escapeHtml(normalizarAtajosTexto(mNum[1]))));
        return;
      }
      var mBul = stripped.match(/^[-*]\s+(.+)$/);
      if (mBul) {
        if (listaTipo !== "ul") { flushLista(); listaTipo = "ul"; }
        listaItems.push(aplicarBadgesLinea(escapeHtml(normalizarAtajosTexto(mBul[1]))));
        return;
      }
      flushLista();
      bloques.push(
        '<p class="lhexia-academy-p">' +
        aplicarBadgesLinea(escapeHtml(normalizarAtajosTexto(stripped))) +
        "</p>"
      );
    });
    flushLista();
    return bloques.join("");
  }

  global.LhexiaAcademyFormat = {
    INVARIANTE_FINANCIERA: INVARIANTE_FINANCIERA,
    escapeHtml: escapeHtml,
    normalizarAtajosTexto: normalizarAtajosTexto,
    formatAcademyRichText: formatAcademyRichText,
  };
})(typeof window !== "undefined" ? window : globalThis);
