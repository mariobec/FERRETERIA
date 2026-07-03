/**
 * UI compartida cola de cobro caja (modales, saldo a favor, SLA).
 */
(function () {
  'use strict';

  function verificarCredito(id) {
    var sel = document.getElementById('metodo_pago_' + id);
    var inp = document.getElementById('monto_recibido_' + id);
    var hint = document.getElementById('hint_monto_' + id);
    var saldoInp = document.getElementById('usar_saldo_favor_' + id);
    var total = parseFloat(inp.dataset.total || inp.min || 0);
    var cliente = inp.dataset.cliente || '';
    var saldo = parseFloat(inp.dataset.saldo || 0);
    var wrapCuotas = document.getElementById('credito_cuotas_wrap_' + id);
    var wrapTrf = document.getElementById('transferencia_ref_wrap_' + id);
    if (!sel || !inp) return;
    if (sel.value === 'Credito') {
      inp.value = 0;
      inp.min = 0;
      inp.step = 'any';
      inp.readOnly = true;
      if (wrapCuotas) wrapCuotas.classList.remove('d-none');
      if (hint) {
        hint.textContent = saldo > 0
          ? ('Venta a crédito: no requiere monto recibido. Atención: ' + cliente + ' ya debe $' + Math.round(saldo).toLocaleString('es-CL') + '.')
          : 'Venta a crédito: no requiere monto recibido en caja.';
      }
    } else {
      if (wrapCuotas) wrapCuotas.classList.add('d-none');
      if (wrapTrf) wrapTrf.classList.toggle('d-none', sel.value !== 'Transferencia');
      if (saldoInp) saldoInp.readOnly = false;
      inp.readOnly = false;
      var saldoFavor = calcularSaldoFavorCobro(id);
      var totalPagar = Math.max(0, total - saldoFavor);
      inp.min = totalPagar;
      inp.step = 'any';
      if (sel.value === 'Transferencia') {
        inp.value = Math.round(totalPagar);
        inp.readOnly = true;
        if (hint) hint.textContent = 'Transferencia: monto exacto del vale. Confirme abono en bandeja antes de entregar.';
      } else if (!inp.value || parseFloat(inp.value) < totalPagar) {
        inp.value = Math.round(totalPagar);
      }
      if (hint && sel.value !== 'Transferencia') {
        hint.textContent = 'Para efectivo, débito o tarjeta debe ser mayor o igual al total pendiente después de saldo a favor.';
      }
    }
    actualizarSaldoFavorCobro(id);
  }

  function formatoCajaCLP(valor) {
    return '$ ' + Math.round(valor || 0).toLocaleString('es-CL');
  }

  function calcularSaldoFavorCobro(id) {
    var saldoInp = document.getElementById('usar_saldo_favor_' + id);
    if (!saldoInp) return 0;
    var disponible = parseFloat(saldoInp.dataset.disponible || 0) || 0;
    var total = parseFloat(saldoInp.dataset.total || 0) || 0;
    var maximo = Math.max(0, Math.min(disponible, total));
    var valor = parseFloat(saldoInp.value || 0) || 0;
    valor = Math.max(0, Math.min(valor, maximo));
    saldoInp.value = Math.round(valor);
    return valor;
  }

  function actualizarSaldoFavorCobro(id) {
    var inp = document.getElementById('monto_recibido_' + id);
    var totalEl = document.getElementById('total_a_pagar_' + id);
    if (!inp) return;
    var total = parseFloat(inp.dataset.total || 0) || 0;
    var saldoFavor = calcularSaldoFavorCobro(id);
    var totalPagar = Math.max(0, total - saldoFavor);
    inp.min = totalPagar;
    if (totalPagar <= 0 && !inp.readOnly) inp.value = 0;
    if (!inp.readOnly && (!inp.value || parseFloat(inp.value) < totalPagar)) {
      inp.value = Math.round(totalPagar);
    }
    if (totalEl) totalEl.textContent = formatoCajaCLP(totalPagar);
  }

  function usarMaximoSaldoFavor(id) {
    var saldoInp = document.getElementById('usar_saldo_favor_' + id);
    if (!saldoInp || saldoInp.readOnly) return;
    var disponible = parseFloat(saldoInp.dataset.disponible || 0) || 0;
    var total = parseFloat(saldoInp.dataset.total || 0) || 0;
    saldoInp.value = Math.round(Math.max(0, Math.min(disponible, total)));
    actualizarSaldoFavorCobro(id);
  }

  function manejarEnvioSeguro(form) {
    var montoInput = form.querySelector('input[name="monto_recibido"]');
    if (montoInput && !montoInput.value && parseFloat(montoInput.min || 0) <= 0) {
      montoInput.value = 0;
    }
    var btn = form.querySelector('button[type="submit"]');
    btn.disabled = true;
    btn.innerHTML = '<i class="fas fa-spinner fa-spin me-2"></i> PROCESANDO...';
    return true;
  }

  window.verificarCredito = verificarCredito;
  window.actualizarSaldoFavorCobro = actualizarSaldoFavorCobro;
  window.usarMaximoSaldoFavor = usarMaximoSaldoFavor;
  window.manejarEnvioSeguro = manejarEnvioSeguro;

  document.addEventListener('DOMContentLoaded', function () {
    var portal = document.getElementById('cajaModalesPortal');
    if (portal) {
      portal.querySelectorAll('.modal').forEach(function (modalEl) {
        document.body.appendChild(modalEl);
      });
      portal.remove();
    }

    document.querySelectorAll('.modal-premium[id^="modalCobro"]').forEach(function (modalEl) {
      modalEl.addEventListener('show.bs.modal', function () {
        document.querySelectorAll('.modal-backdrop').forEach(function (bd, i, list) {
          if (i < list.length - 1) bd.remove();
        });
      });
      modalEl.addEventListener('shown.bs.modal', function () {
        var body = modalEl.querySelector('.modal-body');
        if (body) body.scrollTop = 0;
      });
    });

    if (typeof window._cajaSlaInit === 'function') window._cajaSlaInit();
  });

  (function cajaValeSlaPoll() {
    var cfgEl = document.getElementById('caja-sla-config');
    if (!cfgEl) return;
    var cfg = {};
    try { cfg = JSON.parse(cfgEl.textContent || '{}'); } catch (e) { return; }
    var pollUrl = cfg.pollUrl || '';
    if (!pollUrl) return;

    var slaModalInst = null;
    var slaModalValeId = null;
    var slaModalShownKeys = {};
    var SLA_SNOOZE_MS = 5 * 60 * 1000;

    function fmtClp(n) {
      return '$ ' + Math.round(Number(n) || 0).toLocaleString('es-CL');
    }

    function cobroModalAbierto() {
      return !!document.querySelector('.modal-premium[id^="modalCobro"].show');
    }

    function slaSnoozeKey(id) { return 'cajaSlaSnoozeUntil_' + id; }

    function estaSnoozed(id) {
      try {
        var until = parseInt(localStorage.getItem(slaSnoozeKey(id)) || '0', 10);
        return until > Date.now();
      } catch (e) { return false; }
    }

    function posponerSnooze(id) {
      try { localStorage.setItem(slaSnoozeKey(id), String(Date.now() + SLA_SNOOZE_MS)); } catch (e) {}
    }

    function actualizarBadge(v) {
      var row = document.getElementById('cajaRowVale' + v.id);
      if (!row || row.getAttribute('data-caja-sla-pendiente') !== '1') return;
      var badge = document.getElementById('cajaSlaBadge' + v.id);
      var isProto = document.body.classList.contains('page-caja-prototipo');
      row.classList.remove('caja-row-sla-attention', 'caja-row-sla-delayed', 'caja-row-sla-critical');
      if (!badge) return;
      if ((v.tier || 0) >= 1) {
        badge.textContent = v.label || (v.minutos + ' min');
        if (isProto) {
          badge.className = 'caja-proto-badge caja-proto-badge--sla caja-sla-badge--' + (v.css || 'sla-attention');
        } else {
          badge.className = 'badge rounded-pill caja-sla-badge caja-sla-badge--' + (v.css || 'sla-attention');
        }
        badge.classList.remove('d-none');
        row.classList.add((v.tier || 0) >= 2 ? 'caja-row-sla-delayed' : 'caja-row-sla-attention');
      } else {
        badge.classList.add('d-none');
      }
    }

    function actualizarBanner(data) {
      var wrap = document.getElementById('cajaSlaBannerWrap');
      var banner = document.getElementById('cajaSlaBanner');
      if (!wrap || !banner) return;
      var nModal = data.n_modal || 0;
      var nAtencion = data.n_atencion || 0;
      if (nModal > 0) {
        wrap.classList.remove('d-none');
        banner.className = 'caja-proto-sla caja-proto-sla--critical';
        banner.textContent = nModal === 1
          ? 'Atención: 1 vale lleva más de 15 minutos sin cobrar.'
          : ('Atención: ' + nModal + ' vales llevan más de 15 minutos sin cobrar.');
      } else if (nAtencion > 0) {
        wrap.classList.remove('d-none');
        banner.className = 'caja-proto-sla';
        banner.textContent = nAtencion === 1
          ? 'Hay 1 vale con más de 10 minutos en cola.'
          : ('Hay ' + nAtencion + ' vales con más de 10 minutos en cola.');
      } else {
        wrap.classList.add('d-none');
        banner.textContent = '';
      }
    }

    function abrirModalSla(v) {
      if (typeof bootstrap === 'undefined') return;
      if (cobroModalAbierto()) return;
      if (estaSnoozed(v.id)) return;
      var key = String(v.id) + ':' + String(v.minutos || 0);
      if (slaModalShownKeys[key]) return;
      var modalEl = document.getElementById('modalCajaSlaRecordatorio');
      if (!modalEl) return;
      slaModalValeId = v.id;
      var txt = document.getElementById('cajaSlaModalText');
      var monto = document.getElementById('cajaSlaModalMonto');
      var meta = document.getElementById('cajaSlaModalMeta');
      if (txt) txt.textContent = 'Vale #' + v.id + ' lleva ' + (v.minutos || 0) + ' minutos sin cobrar.';
      if (monto) monto.textContent = fmtClp(v.monto);
      if (meta) {
        meta.textContent = (v.usuario ? ('Vendedor: ' + v.usuario) : '') +
          (v.tiene_despacho_bodega ? ' · Despacho bodega' : '');
      }
      slaModalInst = bootstrap.Modal.getOrCreateInstance(modalEl);
      slaModalInst.show();
      slaModalShownKeys[key] = true;
    }

    async function pollSla() {
      try {
        var r = await fetch(pollUrl, { credentials: 'same-origin', headers: { Accept: 'application/json' } });
        if (!r.ok) return;
        var data = await r.json();
        if (!data || !data.ok) return;
        if (data.auto_anulados && data.auto_anulados.length) {
          alert('Se anularon automáticamente por SLA los vales #' + data.auto_anulados.map(function (x) { return x.id; }).join(', #'));
          window.location.reload();
          return;
        }
        (data.vales || []).forEach(actualizarBadge);
        actualizarBanner(data);
        var candidatos = (data.modal_vales || []).slice().sort(function (a, b) {
          return (b.minutos || 0) - (a.minutos || 0);
        });
        for (var i = 0; i < candidatos.length; i++) {
          if ((candidatos[i].tier || 0) >= 2 && !estaSnoozed(candidatos[i].id)) {
            abrirModalSla(candidatos[i]);
            break;
          }
        }
      } catch (e) {}
    }

    window._cajaSlaInit = function () {
      var btnCobrar = document.getElementById('cajaSlaBtnCobrar');
      var btnPosponer = document.getElementById('cajaSlaBtnPosponer');
      if (btnCobrar) {
        btnCobrar.addEventListener('click', function () {
          if (!slaModalValeId) return;
          var target = document.getElementById('modalCobro' + slaModalValeId);
          if (slaModalInst) slaModalInst.hide();
          if (target && typeof bootstrap !== 'undefined') {
            bootstrap.Modal.getOrCreateInstance(target).show();
          }
        });
      }
      if (btnPosponer) {
        btnPosponer.addEventListener('click', function () {
          if (slaModalValeId) posponerSnooze(slaModalValeId);
          if (slaModalInst) slaModalInst.hide();
        });
      }
      pollSla();
      setInterval(pollSla, 30000);
    };
  })();
})();
