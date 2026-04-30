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

  const DEBOUNCE_PERSIST_MS = 650;
  const persistTimers = {};

  function cancelPersistDetalle(detalleId) {
    if (persistTimers[detalleId]) {
      clearTimeout(persistTimers[detalleId]);
      delete persistTimers[detalleId];
    }
  }

  function schedulePersistDetalle(detalleId, urlActualizarItem) {
    cancelPersistDetalle(detalleId);
    persistTimers[detalleId] = setTimeout(function () {
      delete persistTimers[detalleId];
      actualizarItem(detalleId, urlActualizarItem);
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

  function actualizarItem(detalleId, urlActualizarItem) {
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

    document.body.appendChild(form);
    mostrarPosToast("Guardando cambios del item...");
    form.submit();
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
    const tel = document.getElementById("cliente_telefono");
    const mail = document.getElementById("cliente_correo");
    const status = document.getElementById("clienteStatus");
    [rut, nombre, dir, tel, mail].forEach(function (el) {
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
    const telefono = document.getElementById("cliente_telefono");
    const correo = document.getElementById("cliente_correo");
    const rut = (rutInput.value || "").trim();
    if (!rut) return;
    if (!validarRutCliente()) return;
    try {
      const res = await fetch(urlConsultarCliente + "?rut=" + encodeURIComponent(rut));
      const data = await res.json();
      if (data.existe) {
        nombre.value = data.cliente.nombre || "";
        direccion.value = data.cliente.direccion || "";
        telefono.value = data.cliente.telefono || "";
        correo.value = data.cliente.correo || "";
        status.innerHTML =
          '<span class="text-success"><i class="fas fa-check-circle me-1"></i>Cliente encontrado. Datos cargados.</span>';
      } else {
        nombre.value = "";
        direccion.value = "";
        telefono.value = "";
        correo.value = "";
        status.innerHTML =
          '<span class="text-warning"><i class="fas fa-user-plus me-1"></i>Cliente no registrado. Complete nombre para crearlo al emitir vale.</span>';
      }
    } catch (err) {
      status.innerHTML =
        '<span class="text-danger"><i class="fas fa-exclamation-triangle me-1"></i>No se pudo consultar cliente.</span>';
    }
  }

  document.addEventListener("DOMContentLoaded", function () {
    const cfg = readPosConfig();
    if (!cfg || !cfg.urls) return;
    const u = cfg.urls;

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
      $("#buscarProducto").select2({
        theme: "bootstrap-5",
        placeholder: "Escriba nombre o código de barra...",
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
          data: (params) => ({ q: params.term }),
          processResults: (data) => ({ results: data.results }),
          cache: true,
        },
      });
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

    $(".cantidad-input, .descuento-input").on("input change", function () {
      const detalleId = $(this).data("detalle-id");
      const precio = parseFloat($(this).data("precio")) || 0;
      actualizarSubtotal(detalleId, precio);
      actualizarEstadoValidacionStock();
      schedulePersistDetalle(detalleId, u.actualizar_item);
    });

    $(".btn-ajustar-cantidad").on("click", function () {
      const detalleId = parseInt($(this).data("detalle-id"), 10);
      const delta = parseInt($(this).data("delta"), 10);
      const precio = parseFloat($(this).data("precio")) || 0;
      ajustarCantidad(detalleId, delta, precio);
      actualizarEstadoValidacionStock();
      schedulePersistDetalle(detalleId, u.actualizar_item);
    });

    $(".btn-actualizar-item").on("click", function () {
      const detalleId = parseInt($(this).data("detalle-id"), 10);
      cancelPersistDetalle(detalleId);
      actualizarItem(detalleId, u.actualizar_item);
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
