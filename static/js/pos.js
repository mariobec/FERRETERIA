/**
 * Punto de venta: buscador, líneas, cliente y atajos.
 * URLs inyectadas desde #pos-config (JSON).
 */
(function () {
  function readPosConfig() {
    const el = document.getElementById("pos-config");
    if (!el || !el.textContent) return null;
    try {
      return JSON.parse(el.textContent);
    } catch (e) {
      return null;
    }
  }

  function formatoCLP(valor) {
    return new Intl.NumberFormat("es-CL", { style: "currency", currency: "CLP" }).format(valor);
  }

  function actualizarSubtotal(detalleId, precioUnitario) {
    const cantidad = parseFloat(document.getElementById("cantidad_" + detalleId).value) || 0;
    const descuento = parseFloat(document.getElementById("descuento_" + detalleId).value) || 0;
    const factorStock = parseFloat(document.getElementById("cantidad_" + detalleId).dataset.factorStock || "1") || 1;
    const subtotal = cantidad * precioUnitario * (1 - descuento / 100);
    document.getElementById("subtotal_" + detalleId).innerText = formatoCLP(subtotal);
    const consumoEl = document.getElementById("consumo_stock_" + detalleId);
    if (consumoEl) {
      consumoEl.innerText = Math.max(0, Math.round(cantidad * factorStock));
    }

    let total = 0;
    document.querySelectorAll("[id^='subtotal_']").forEach(function (cell) {
      const valor = cell.innerText.replace(/[^0-9]/g, "");
      total += parseFloat(valor) || 0;
    });
    document.getElementById("monto_total").innerText = formatoCLP(total);
    document.getElementById("precio_unitario_" + detalleId).innerText = formatoCLP(precioUnitario);
  }

  function validarStockLinea(detalleId) {
    const cantidadEl = document.getElementById("cantidad_" + detalleId);
    if (!cantidadEl) return false;
    const cantidad = parseFloat(cantidadEl.value) || 0;
    const factorStock = parseFloat(cantidadEl.dataset.factorStock || "1") || 1;
    const stockDisponible = parseFloat(cantidadEl.dataset.stockDisponible || "0") || 0;
    const consumo = Math.max(0, Math.round(cantidad * factorStock));
    const excede = consumo > stockDisponible;

    const row = document.getElementById("pos_row_" + detalleId);
    const alertEl = document.getElementById("stock_alert_" + detalleId);
    if (row) row.classList.toggle("pos-row-stock-error", excede);
    if (alertEl) alertEl.classList.toggle("d-none", !excede);
    return excede;
  }

  function actualizarEstadoValidacionStock() {
    let hayExceso = false;
    document.querySelectorAll(".cantidad-input").forEach(function (input) {
      const detalleId = input.dataset.detalleId;
      if (!detalleId) return;
      if (validarStockLinea(detalleId)) hayExceso = true;
    });
    const alertaGlobal = document.getElementById("stockValidationAlert");
    if (alertaGlobal) alertaGlobal.classList.toggle("d-none", !hayExceso);
    const btnEmitir = document.getElementById("emitirValeBtn");
    if (btnEmitir) btnEmitir.disabled = hayExceso;
  }

  function ajustarCantidad(detalleId, delta, precioUnitario) {
    const input = document.getElementById("cantidad_" + detalleId);
    let actual = parseInt(input.value || "1", 10);
    actual = Math.max(1, actual + delta);
    input.value = actual;
    actualizarSubtotal(detalleId, precioUnitario);
  }

  function mostrarPosToast(mensaje) {
    const body = document.getElementById("posToastBody");
    if (!body) return;
    body.innerText = mensaje;
    const toastEl = document.getElementById("posToast");
    if (!toastEl || typeof bootstrap === "undefined") return;
    const toast = bootstrap.Toast.getOrCreateInstance(toastEl, { delay: 1500 });
    toast.show();
  }

  function escapeHtmlPosJs(str) {
    if (str == null || str === "") return "";
    const d = document.createElement("div");
    d.textContent = str;
    return d.innerHTML;
  }

  const DEBOUNCE_PERSIST_MS = 650;
  const EPS_DESC = 1e-6;
  const persistTimers = {};
  let pendingDetalleIdAutorizacionDesc = null;

  function cancelPersistDetalle(detalleId) {
    if (persistTimers[detalleId]) {
      clearTimeout(persistTimers[detalleId]);
      delete persistTimers[detalleId];
    }
  }

  function schedulePersistDetalle(detalleId, urlActualizarItem, soloCantidad) {
    cancelPersistDetalle(detalleId);
    persistTimers[detalleId] = setTimeout(function () {
      delete persistTimers[detalleId];
      actualizarItem(detalleId, urlActualizarItem, { solo_cantidad: !!soloCantidad });
    }, DEBOUNCE_PERSIST_MS);
  }

  function isTypingInField(target) {
    if (!target || !target.tagName) return false;
    const t = target.tagName.toUpperCase();
    if (t === "TEXTAREA" || t === "SELECT") return true;
    if (t === "INPUT") {
      const type = (target.type || "").toLowerCase();
      if (["button", "submit", "checkbox", "radio", "range", "file", "hidden"].indexOf(type) !== -1) {
        return false;
      }
      return true;
    }
    return false;
  }

  function actualizarItem(detalleId, urlActualizarItem, opts) {
    opts = opts || {};
    const cantidad = document.getElementById("cantidad_" + detalleId).value;
    const descuento = document.getElementById("descuento_" + detalleId).value;
    const form = document.createElement("form");
    form.method = "POST";
    form.action = urlActualizarItem;

    const fActualizar = document.createElement("input");
    fActualizar.type = "hidden";
    fActualizar.name = "actualizar";
    fActualizar.value = detalleId;
    form.appendChild(fActualizar);

    if (opts.solo_cantidad) {
      const fs = document.createElement("input");
      fs.type = "hidden";
      fs.name = "solo_cantidad";
      fs.value = "1";
      form.appendChild(fs);
    }

    const fCantidad = document.createElement("input");
    fCantidad.type = "hidden";
    fCantidad.name = "cantidad_" + detalleId;
    fCantidad.value = cantidad;
    form.appendChild(fCantidad);

    const fDescuento = document.createElement("input");
    fDescuento.type = "hidden";
    fDescuento.name = "descuento_" + detalleId;
    fDescuento.value = descuento;
    form.appendChild(fDescuento);

    if (opts.supervisor_identificador) {
      const fc = document.createElement("input");
      fc.type = "hidden";
      fc.name = "supervisor_identificador";
      fc.value = opts.supervisor_identificador;
      form.appendChild(fc);
    }
    if (opts.supervisor_clave) {
      const fp = document.createElement("input");
      fp.type = "hidden";
      fp.name = "supervisor_clave";
      fp.value = opts.supervisor_clave;
      form.appendChild(fp);
    }

    document.body.appendChild(form);
    mostrarPosToast(opts.solo_cantidad ? "Guardando cantidad..." : "Guardando cambios del item...");
    form.submit();
  }

  function descuentoRequiereCredencialSupervisor(detalleId, descLibre) {
    if (descLibre) return false;
    const descEl = document.getElementById("descuento_" + detalleId);
    if (!descEl) return false;
    const descServidor = parseFloat(descEl.dataset.descuentoServidor || "0") || 0;
    const descNuevo = parseFloat(descEl.value || "0") || 0;
    return descNuevo > descServidor + EPS_DESC;
  }

  function validarRutCliente() {
    const chk = document.getElementById("cliente_final");
    const rutErr = document.getElementById("rut_error");
    if (chk && chk.checked) {
      if (rutErr) rutErr.classList.add("d-none");
      return true;
    }
    const rut = document.getElementById("cliente_rut").value.replace(/\./g, "").replace(/-/g, "").toUpperCase();
    if (!rut || rut.length < 8) {
      if (rutErr) rutErr.classList.remove("d-none");
      return false;
    }
    const cuerpo = rut.slice(0, -1);
    const dvIngresado = rut.slice(-1);
    let suma = 0;
    const factores = [2, 3, 4, 5, 6, 7];
    let i = 0;
    for (let j = cuerpo.length - 1; j >= 0; j--) {
      suma += parseInt(cuerpo[j], 10) * factores[i];
      i = (i + 1) % 6;
    }
    const resto = 11 - (suma % 11);
    const dvEsperado = resto === 11 ? "0" : resto === 10 ? "K" : resto.toString();
    if (dvIngresado !== dvEsperado) {
      if (rutErr) rutErr.classList.remove("d-none");
      return false;
    }
    if (rutErr) rutErr.classList.add("d-none");
    return true;
  }

  function syncClienteFinalMode() {
    const chk = document.getElementById("cliente_final");
    if (!chk) return;
    const finalMode = chk.checked;
    const rut = document.getElementById("cliente_rut");
    const nombre = document.getElementById("cliente_nombre");
    const btn = document.getElementById("buscarClienteBtn");
    const dir = document.getElementById("cliente_direccion");
    const giro = document.getElementById("cliente_giro");
    const comuna = document.getElementById("cliente_comuna");
    const ciudad = document.getElementById("cliente_ciudad");
    const tel = document.getElementById("cliente_telefono");
    const mail = document.getElementById("cliente_correo");
    const status = document.getElementById("clienteStatus");
    [rut, nombre, dir, giro, comuna, ciudad, tel, mail].forEach(function (el) {
      if (!el) return;
      el.disabled = finalMode;
    });
    if (btn) btn.disabled = finalMode;
    if (rut) {
      rut.required = !finalMode;
      if (finalMode) {
        rut.value = "";
        rut.removeAttribute("required");
      } else {
        rut.setAttribute("required", "required");
      }
    }
    if (status) {
      status.innerHTML = finalMode
        ? '<span class="text-secondary"><i class="fas fa-user me-1"></i>Se usará el cliente genérico (boleta sin datos).</span>'
        : "";
    }
  }

  async function buscarClientePorRut(urlConsultarCliente) {
    const rutInput = document.getElementById("cliente_rut");
    const status = document.getElementById("clienteStatus");
    const nombre = document.getElementById("cliente_nombre");
    const direccion = document.getElementById("cliente_direccion");
    const giro = document.getElementById("cliente_giro");
    const comuna = document.getElementById("cliente_comuna");
    const ciudad = document.getElementById("cliente_ciudad");
    const telefono = document.getElementById("cliente_telefono");
    const correo = document.getElementById("cliente_correo");
    const rut = (rutInput.value || "").trim();
    if (!rut) return;
    if (!validarRutCliente()) return;
    try {
      const res = await fetch(urlConsultarCliente + "?rut=" + encodeURIComponent(rut), {
        credentials: "same-origin",
        headers: { Accept: "application/json" },
      });
      const ct = (res.headers.get("content-type") || "").toLowerCase();
      const rawText = await res.text();
      let data = null;
      if (ct.indexOf("application/json") !== -1) {
        try {
          data = JSON.parse(rawText);
        } catch (e) {
          data = null;
        }
      }
      if (!res.ok) {
        let detalle = "Código HTTP " + res.status + ".";
        if (data && data.mensaje) detalle = escapeHtmlPosJs(String(data.mensaje).slice(0, 400));
        else if (res.status === 401 || res.status === 302) detalle = "Sesión expirada; vuelva a iniciar sesión.";
        status.innerHTML =
          '<span class="text-danger"><i class="fas fa-exclamation-triangle me-1"></i>No se pudo consultar cliente. ' +
          detalle +
          "</span>";
        return;
      }
      if (!data) {
        status.innerHTML =
          '<span class="text-danger"><i class="fas fa-exclamation-triangle me-1"></i>Respuesta inválida del servidor.</span>';
        return;
      }
      if (data.existe) {
        nombre.value = data.cliente.nombre || "";
        direccion.value = data.cliente.direccion || "";
        if (giro) giro.value = data.cliente.giro || "";
        if (comuna) comuna.value = data.cliente.comuna || "";
        if (ciudad) ciudad.value = data.cliente.ciudad || "";
        telefono.value = data.cliente.telefono || "";
        correo.value = data.cliente.correo || "";
        status.innerHTML =
          '<span class="text-success"><i class="fas fa-check-circle me-1"></i>Cliente encontrado. Datos cargados.</span>';
      } else {
        nombre.value = "";
        direccion.value = "";
        if (giro) giro.value = "";
        if (comuna) comuna.value = "";
        if (ciudad) ciudad.value = "";
        telefono.value = "";
        correo.value = "";
        status.innerHTML =
          '<span class="text-warning"><i class="fas fa-user-plus me-1"></i>Cliente no registrado. Complete nombre para crearlo al emitir vale.</span>';
      }
    } catch (err) {
      status.innerHTML =
        '<span class="text-danger"><i class="fas fa-exclamation-triangle me-1"></i>No se pudo consultar cliente (red o respuesta inválida).</span>';
    }
  }

  document.addEventListener("DOMContentLoaded", function () {
    const cfg = readPosConfig();
    if (!cfg || !cfg.urls) return;
    const u = cfg.urls;
    const descLibre = !!cfg.descuento_libre;
    let posAutorizadoresCache = [];

    function escapeHtmlPos(str) {
      if (str == null || str === "") return "";
      const d = document.createElement("div");
      d.textContent = str;
      return d.innerHTML;
    }

    function posFiltrarMostrarSugerenciasSupervisor() {
      const input = document.getElementById("posSupervisorIdentificador");
      const wrap = document.getElementById("posSupervisorSuggestWrap");
      if (!input || !wrap) return;
      const q = (input.value || "").trim().toLowerCase();
      const list = posAutorizadoresCache || [];
      let match = [];
      if (!q) {
        match = list.slice(0, 12);
      } else {
        match = list
          .filter(function (row) {
            const nom = (row.nombre || "").toLowerCase();
            const cor = (row.correo || "").toLowerCase();
            return nom.indexOf(q) !== -1 || cor.indexOf(q) !== -1;
          })
          .slice(0, 12);
      }
      wrap.innerHTML = "";
      if (match.length === 0) {
        wrap.classList.add("d-none");
        return;
      }
      match.forEach(function (row) {
        const btn = document.createElement("button");
        btn.type = "button";
        btn.className = "list-group-item list-group-item-action py-2 px-3 text-start border-0 border-bottom";
        btn.innerHTML =
          '<div class="fw-semibold">' +
          escapeHtmlPos(row.nombre) +
          '</div><div class="small text-muted text-truncate">' +
          escapeHtmlPos(row.correo) +
          "</div>";
        btn.addEventListener("click", function () {
          input.value = row.correo || "";
          wrap.classList.add("d-none");
          wrap.innerHTML = "";
          const pwdEl = document.getElementById("posSupervisorClave");
          if (pwdEl) pwdEl.focus();
        });
        wrap.appendChild(btn);
      });
      wrap.classList.remove("d-none");
    }

    function posSupervisorSuggestOutside(e) {
      const wrap = document.getElementById("posSupervisorSuggestWrap");
      const input = document.getElementById("posSupervisorIdentificador");
      if (!wrap || !input || wrap.classList.contains("d-none")) return;
      const t = e.target;
      if (wrap.contains(t) || input.contains(t)) return;
      wrap.classList.add("d-none");
    }

    document.addEventListener("mousedown", posSupervisorSuggestOutside);

    const modalAutorizaEl = document.getElementById("modalAutorizarDescuentoPos");
    if (modalAutorizaEl && typeof bootstrap !== "undefined") {
      modalAutorizaEl.addEventListener("shown.bs.modal", function () {
        const inputSup = document.getElementById("posSupervisorIdentificador");
        const urlUsu = u.usuarios_autorizar_descuento;
        function postFetch() {
          posFiltrarMostrarSugerenciasSupervisor();
          if (inputSup) inputSup.focus();
        }
        if (!urlUsu) {
          posAutorizadoresCache = [];
          postFetch();
          return;
        }
        fetch(urlUsu)
          .then(function (r) {
            return r.json();
          })
          .then(function (data) {
            posAutorizadoresCache = data.usuarios || [];
          })
          .catch(function () {
            posAutorizadoresCache = [];
          })
          .finally(postFetch);
      });
      modalAutorizaEl.addEventListener("hidden.bs.modal", function () {
        pendingDetalleIdAutorizacionDesc = null;
        const idEl = document.getElementById("posSupervisorIdentificador");
        const p = document.getElementById("posSupervisorClave");
        const wrap = document.getElementById("posSupervisorSuggestWrap");
        if (idEl) idEl.value = "";
        if (p) p.value = "";
        if (wrap) {
          wrap.classList.add("d-none");
          wrap.innerHTML = "";
        }
      });
      const btnConf = document.getElementById("posConfirmarAutorizacionDescuento");
      if (btnConf) {
        btnConf.addEventListener("click", function () {
          const ident = (document.getElementById("posSupervisorIdentificador") || {}).value;
          const pwd = (document.getElementById("posSupervisorClave") || {}).value;
          const identTrim = (ident || "").trim();
          if (!identTrim || !pwd) {
            mostrarPosToast("Ingrese supervisor y contraseña.");
            return;
          }
          const detalleId = pendingDetalleIdAutorizacionDesc;
          if (detalleId == null) return;
          pendingDetalleIdAutorizacionDesc = null;
          const modalInst = bootstrap.Modal.getInstance(modalAutorizaEl);
          if (modalInst) modalInst.hide();
          actualizarItem(detalleId, u.actualizar_item, {
            supervisor_identificador: identTrim,
            supervisor_clave: pwd,
          });
        });
      }
    }

    const supInputPos = document.getElementById("posSupervisorIdentificador");
    if (supInputPos) {
      supInputPos.addEventListener("input", posFiltrarMostrarSugerenciasSupervisor);
      supInputPos.addEventListener("focus", posFiltrarMostrarSugerenciasSupervisor);
    }

    const rutEl = document.getElementById("cliente_rut");
    if (rutEl) {
      rutEl.addEventListener("input", function (e) {
        let rut = e.target.value.replace(/\./g, "").replace(/-/g, "").toUpperCase();
        if (rut.length > 1) {
          const cuerpo = rut.slice(0, -1);
          const dv = rut.slice(-1);
          const cFmt = cuerpo.replace(/\B(?=(\d{3})+(?!\d))/g, ".");
          e.target.value = cFmt + "-" + dv;
        }
      });
    }

    const chkFinal = document.getElementById("cliente_final");
    if (chkFinal) {
      chkFinal.addEventListener("change", syncClienteFinalMode);
      syncClienteFinalMode();
    }

    const formEmitir = document.getElementById("formEmitirVale");
    if (formEmitir) {
      formEmitir.addEventListener("submit", function (e) {
        actualizarEstadoValidacionStock();
        if (document.getElementById("emitirValeBtn")?.disabled) {
          e.preventDefault();
          mostrarPosToast("Corrija items con stock insuficiente antes de emitir.");
          return;
        }
        if (!validarRutCliente()) e.preventDefault();
      });
    }

    if ($("#buscarProducto").length) {
      function posSoloVendiblesActivo() {
        const chk = document.getElementById("posSoloVendibles");
        return !!(chk && chk.checked);
      }

      $("#buscarProducto").select2({
        theme: "bootstrap-5",
        placeholder: "Nombre, código de barras, interno o referencia…",
        allowClear: true,
        minimumInputLength: 2,
        language: {
          inputTooShort: () => "Por favor, introduzca 2 o más caracteres",
          noResults: () => "No se encontraron productos",
          searching: () => "Buscando...",
        },
        ajax: {
          url: u.buscar_producto,
          dataType: "json",
          delay: 300,
          data: function (params) {
            return {
              q: params.term,
              solo_vendibles: posSoloVendiblesActivo() ? "1" : "0",
              origen: "pos",
            };
          },
          processResults: (data) => ({ results: data.results }),
          cache: false,
        },
      });

      const chkVend = document.getElementById("posSoloVendibles");
      function syncPosFiltroBusquedaBotones() {
        const bV = document.getElementById("posBtnFiltroVenta");
        const bC = document.getElementById("posBtnFiltroCatalogo");
        if (!chkVend || !bV || !bC) return;
        const strict = !!chkVend.checked;
        bV.classList.toggle("btn-primary", strict);
        bV.classList.toggle("btn-outline-secondary", !strict);
        bC.classList.toggle("btn-primary", !strict);
        bC.classList.toggle("btn-outline-secondary", strict);
      }
      if (chkVend) {
        chkVend.addEventListener("change", function () {
          syncPosFiltroBusquedaBotones();
          const $sel = $("#buscarProducto");
          $sel.val(null).trigger("change");
        });
      }
      const bVenta = document.getElementById("posBtnFiltroVenta");
      const bCat = document.getElementById("posBtnFiltroCatalogo");
      if (chkVend && bVenta && bCat) {
        bVenta.addEventListener("click", function () {
          chkVend.checked = true;
          chkVend.dispatchEvent(new Event("change"));
        });
        bCat.addEventListener("click", function () {
          chkVend.checked = false;
          chkVend.dispatchEvent(new Event("change"));
        });
        syncPosFiltroBusquedaBotones();
      }
    }

    document.querySelectorAll("[id^='precio_unitario_']").forEach(function (cell) {
      const valor = parseFloat(cell.innerText) || 0;
      cell.innerText = formatoCLP(valor);
    });
    document.querySelectorAll("[id^='subtotal_']").forEach(function (cell) {
      const valor = parseFloat(cell.innerText) || 0;
      cell.innerText = formatoCLP(valor);
    });
    const mt = document.getElementById("monto_total");
    if (mt) {
      const totalInicial = parseFloat(mt.innerText.replace(/[^0-9.-]/g, "")) || 0;
      mt.innerText = formatoCLP(totalInicial);
    }

    $("#buscarClienteBtn").on("click", function () {
      buscarClientePorRut(u.consultar_cliente);
    });
    $("#cliente_rut").on("blur", function () {
      buscarClientePorRut(u.consultar_cliente);
    });

    $(".cantidad-input").on("input change", function () {
      const detalleId = $(this).data("detalle-id");
      const precio = parseFloat($(this).data("precio")) || 0;
      actualizarSubtotal(detalleId, precio);
      actualizarEstadoValidacionStock();
      schedulePersistDetalle(detalleId, u.actualizar_item, true);
    });

    $(".descuento-input").on("input change", function () {
      const detalleId = $(this).data("detalle-id");
      const precio = parseFloat($(this).data("precio")) || 0;
      actualizarSubtotal(detalleId, precio);
      actualizarEstadoValidacionStock();
      // El descuento solo se guarda en servidor al pulsar "Actualizar" (así puede pedirse supervisor).
    });

    $(".btn-ajustar-cantidad").on("click", function () {
      const detalleId = parseInt($(this).data("detalle-id"), 10);
      const delta = parseInt($(this).data("delta"), 10);
      const precio = parseFloat($(this).data("precio")) || 0;
      ajustarCantidad(detalleId, delta, precio);
      actualizarEstadoValidacionStock();
      schedulePersistDetalle(detalleId, u.actualizar_item, true);
    });

    $(".btn-actualizar-item").on("click", function () {
      const detalleId = parseInt($(this).data("detalle-id"), 10);
      cancelPersistDetalle(detalleId);
      if (descuentoRequiereCredencialSupervisor(detalleId, descLibre)) {
        pendingDetalleIdAutorizacionDesc = detalleId;
        if (modalAutorizaEl && typeof bootstrap !== "undefined") {
          const modalInst = bootstrap.Modal.getOrCreateInstance(modalAutorizaEl);
          modalInst.show();
        } else {
          mostrarPosToast("No se pudo abrir la autorización. Recargue la página.");
        }
        return;
      }
      actualizarItem(detalleId, u.actualizar_item, {});
    });

    actualizarEstadoValidacionStock();

    const tbodyPos = document.querySelector(".table-ds tbody");
    if (tbodyPos) {
      tbodyPos.addEventListener("focusin", function (e) {
        const tr = e.target.closest("tr");
        if (!tr || !tbodyPos.contains(tr)) return;
        tbodyPos.querySelectorAll("tr.pos-row-active").forEach(function (r) {
          r.classList.remove("pos-row-active");
        });
        tr.classList.add("pos-row-active");
      });
    }

    document.addEventListener("keydown", function (e) {
      if (e.key === "F2") {
        e.preventDefault();
        $("#buscarProducto").select2("open");
      }
      if (e.key === "F3") {
        if (isTypingInField(e.target)) return;
        e.preventDefault();
        const chk = document.getElementById("cliente_final");
        if (!chk) return;
        chk.checked = !chk.checked;
        chk.dispatchEvent(new Event("change", { bubbles: true }));
      }
      if (e.key === "F4") {
        e.preventDefault();
        const btn = document.getElementById("emitirValeBtn");
        if (btn) btn.click();
      }
    });
  });
})();
