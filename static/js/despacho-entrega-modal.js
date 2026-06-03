/**
 * QR ticket → modal registro de entrega (tienda / bodega).
 */
(function () {
  'use strict';

  function cfg() {
    var el = document.getElementById('despachoEntregaConfig');
    if (!el || !el.textContent) return null;
    try {
      return JSON.parse(el.textContent);
    } catch (e) {
      return null;
    }
  }

  function fmtMsg(data) {
    if (!data) return 'Error de red.';
    return data.mensaje || data.error || 'No se pudo registrar la entrega.';
  }

  async function postEntrega(url, body) {
    var r = await fetch(url, {
      method: 'POST',
      credentials: 'same-origin',
      headers: { 'Content-Type': 'application/json', Accept: 'application/json' },
      body: JSON.stringify(body || {}),
    });
    var data = await r.json().catch(function () {
      return { ok: false, mensaje: 'Respuesta inválida.' };
    });
    if (!r.ok && data.ok !== false) data.ok = false;
    return data;
  }

  function actualizarUiResumen(data) {
    var badge = document.getElementById('entregaEstadoBadge');
    if (badge && data.estado) {
      badge.textContent = data.estado;
      badge.className = 'badge ' + (data.completa ? 'bg-success' : 'bg-warning text-dark');
    }
    if (data.completa) {
      var btnTodo = document.getElementById('btnEntregaTodo');
      if (btnTodo) btnTodo.disabled = true;
    }
  }

  function syncFilas(lineas) {
    if (!lineas || !lineas.length) return;
    lineas.forEach(function (ln) {
      var tr = document.querySelector('tr[data-detalle-id="' + ln.detalle_id + '"]');
      if (!tr) return;
      var ent = tr.querySelector('.entrega-col-entregada');
      var pend = tr.querySelector('.entrega-col-pendiente');
      var btn = tr.querySelector('.btn-entrega-linea');
      if (ent) ent.textContent = ln.entregada;
      if (pend) pend.textContent = ln.pendiente;
      if (btn) {
        btn.disabled = !(ln.pendiente > 0);
        btn.textContent = ln.pendiente > 0 ? 'Entregar ' + ln.pendiente : 'Listo';
      }
    });
  }

  async function entregarLinea(detalleId, cantidad) {
    var c = cfg();
    if (!c || !c.registrarUrl) return;
    var btn = document.querySelector('.btn-entrega-linea[data-detalle-id="' + detalleId + '"]');
    if (btn) btn.disabled = true;
    var data = await postEntrega(c.registrarUrl, {
      detalle_id: detalleId,
      cantidad: cantidad,
      token: c.token || '',
    });
    if (data.ok) {
      syncFilas(data.lineas || []);
      actualizarUiResumen(data);
      if (data.completa) {
        alert('Entrega completa. Vale cerrado en sistema.');
      }
    } else {
      alert(fmtMsg(data));
      if (btn) btn.disabled = false;
    }
  }

  async function entregarTodo() {
    var c = cfg();
    if (!c || !c.registrarUrl) return;
    if (!confirm('¿Registrar entrega de todas las líneas pendientes visibles?')) return;
    var data = await postEntrega(c.registrarUrl, { accion: 'entregar_todo', token: c.token || '' });
    if (data.ok) {
      syncFilas(data.lineas || []);
      actualizarUiResumen(data);
      if (data.completa) alert('Entrega completa. Vale cerrado en sistema.');
    } else {
      alert(fmtMsg(data));
    }
  }

  document.addEventListener('DOMContentLoaded', function () {
    var c = cfg();
    var modalEl = document.getElementById('modalEntregaTicket');
    if (!modalEl || typeof bootstrap === 'undefined') return;

    document.querySelectorAll('.btn-entrega-linea').forEach(function (btn) {
      btn.addEventListener('click', function () {
        var detId = parseInt(btn.getAttribute('data-detalle-id'), 10);
        var cant = parseInt(btn.getAttribute('data-pendiente'), 10);
        if (!detId || !cant) return;
        entregarLinea(detId, cant);
      });
    });

    var btnTodo = document.getElementById('btnEntregaTodo');
    if (btnTodo) btnTodo.addEventListener('click', entregarTodo);

    if (c && c.autoAbrirModal && c.estadoPagado && !c.entregaCompleta) {
      bootstrap.Modal.getOrCreateInstance(modalEl).show();
    }
  });
})();
