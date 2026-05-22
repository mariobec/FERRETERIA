/**
 * Buscador folio en /recepciones — inyecta UI si la plantilla en Render aún no trae el input (SD-1).
 */
(function () {
  if (document.getElementById('filtro-folio-rcv')) {
    return;
  }
  var form = document.getElementById('form-filtros-recepciones');
  if (!form) {
    return;
  }
  var params = new URLSearchParams(window.location.search);
  var folioVal = params.get('folio') || '';

  var box = document.createElement('div');
  box.className = 'mb-3 p-3 rounded border border-primary bg-light';
  box.setAttribute('role', 'search');
  box.innerHTML =
    '<label class="form-label fw-bold mb-2" for="filtro-folio-rcv">' +
    '<i class="fas fa-file-invoice me-1"></i> Nº factura / folio SII</label>' +
    '<div class="input-group">' +
    '<input type="search" class="form-control form-control-lg" id="filtro-folio-rcv" ' +
    'name="folio" placeholder="Ej. 4949757" autocomplete="off" inputmode="numeric" ' +
    'value="' + String(folioVal).replace(/"/g, '&quot;') + '">' +
    '<button type="button" class="btn btn-primary" id="btn-buscar-folio-rcv">' +
    '<i class="fas fa-search me-1"></i> Buscar</button>' +
    '</div>' +
    '<p class="small text-muted mb-0 mt-2">Si no ve este cuadro tras un deploy, recargue con Ctrl+F5.</p>';

  var cardBody = form.parentNode;
  if (cardBody) {
    cardBody.insertBefore(box, form);
  }

  var input = document.getElementById('filtro-folio-rcv');
  var btn = document.getElementById('btn-buscar-folio-rcv');
  function irBuscar() {
    var v = (input && input.value ? input.value : '').trim();
    var u = new URL(window.location.href);
    if (v) {
      u.searchParams.set('folio', v);
    } else {
      u.searchParams.delete('folio');
    }
    u.searchParams.delete('page');
    window.location.href = u.toString();
  }
  if (btn) {
    btn.addEventListener('click', irBuscar);
  }
  if (input) {
    input.addEventListener('keydown', function (e) {
      if (e.key === 'Enter') {
        e.preventDefault();
        irBuscar();
      }
    });
    input.focus();
  }
})();
