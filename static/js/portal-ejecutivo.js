(function () {
  'use strict';

  const root = document.getElementById('portalSdRoot');
  if (!root) return;

  let periodo = root.dataset.periodo || 'mes';
  const loading = document.getElementById('portalLoading');

  function fmt(n) {
    const v = Math.round(Number(n) || 0);
    return '$' + Math.abs(v).toLocaleString('es-CL');
  }

  function setLoading(on) {
    if (!loading) return;
    loading.classList.toggle('d-none', !on);
  }

  function renderNotas(el, notas) {
    if (!el || !notas) return;
    el.innerHTML = notas.map((t) => '<li>' + escapeHtml(t) + '</li>').join('');
  }

  function escapeHtml(s) {
    return String(s)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;');
  }

  function renderResumen(d) {
    document.getElementById('portalPeriodoLabel').textContent =
      'Período: ' + (d.periodo_label || d.periodo || '');
    root.querySelector('[data-kpi="ventas"]').textContent = d.ventas_fmt || fmt(d.ventas_clp);
    root.querySelector('[data-kpi="margen"]').textContent =
      (d.margen_bruto_fmt || fmt(d.margen_bruto_clp)) +
      ' (' +
      (d.margen_bruto_pct != null ? d.margen_bruto_pct : 0) +
      '%)';
    root.querySelector('[data-kpi="gastos"]').textContent = d.gastos_op_fmt || fmt(d.gastos_op_clp);
    root.querySelector('[data-kpi="utilidad"]').textContent =
      d.utilidad_operativa_est_fmt || fmt(d.utilidad_operativa_est_clp);
    document.getElementById('portalInversionTotal').textContent =
      d.inversion_total_fmt || fmt(d.inversion_total_clp);
    const des = d.desglose_inversion || {};
    const labels = {
      inventario_clp: 'Inventario (costo)',
      cxc_clp: 'CxC clientes',
      caja_clp: 'Caja abierta',
      activos_fijos_clp: 'Activos fijos',
    };
    const ul = document.getElementById('portalDesgloseInversion');
    ul.innerHTML = Object.keys(labels)
      .map(function (k) {
        return (
          '<li><span>' +
          labels[k] +
          '</span><strong>' +
          fmt(des[k]) +
          '</strong></li>'
        );
      })
      .join('');
    document.getElementById('portalComprometido').textContent = fmt(d.comprometido_compras_clp);
    document.getElementById('portalOcCount').textContent =
      (d.oc_pendientes_count || 0) + ' órdenes de compra pendientes (estimado)';
    const sem = d.ventas_semanales || [];
    const max = Math.max.apply(null, sem.map((w) => w.ventas_clp || 0).concat([1]));
    const meta = d.meta_ventas_semana_clp || 0;
    document.getElementById('portalVentasSemanales').innerHTML = sem
      .map(function (w) {
        const pct = Math.min(100, Math.round(((w.ventas_clp || 0) / max) * 100));
        let extra = '';
        if (meta > 0) {
          extra =
            ' <span class="text-muted">meta ' +
            fmt(meta) +
            '</span>';
        }
        return (
          '<div class="bar-row"><span style="min-width:7rem">' +
          escapeHtml(w.semana) +
          '</span><div class="bar-track"><div class="bar-fill" style="width:' +
          pct +
          '%"></div></div><strong>' +
          fmt(w.ventas_clp) +
          '</strong>' +
          extra +
          '</div>'
        );
      })
      .join('');
    renderNotas(document.getElementById('portalNotasResumen'), d.notas);
  }

  function renderActivos(d) {
    root.querySelector('[data-act="inventario"]').textContent = fmt(d.inventario_clp);
    root.querySelector('[data-act="cxc"]').textContent = fmt(d.cxc_clp);
    root.querySelector('[data-act="caja"]').textContent = fmt(d.caja_clp);
    root.querySelector('[data-act="fijos"]').textContent = fmt(d.activos_fijos_clp);
    root.querySelector('[data-act="rotacion"]').textContent =
      d.rotacion_inventario != null ? String(d.rotacion_inventario) : '—';
    root.querySelector('[data-act="dsi"]').textContent =
      d.dias_stock_inventario != null ? d.dias_stock_inventario + ' d' : '—';
    root.querySelector('[data-act="dias_cxc"]').textContent =
      d.dias_cxc_est != null ? d.dias_cxc_est + ' d' : '—';
    root.querySelector('[data-act="apal"]').textContent =
      (d.apalancamiento_operativo_pct != null ? d.apalancamiento_operativo_pct : 0) + '%';
    renderNotas(document.getElementById('portalNotasActivos'), d.notas);
  }

  async function fetchJson(url) {
    const r = await fetch(url, { credentials: 'same-origin', headers: { Accept: 'application/json' } });
    if (!r.ok) throw new Error('HTTP ' + r.status);
    return r.json();
  }

  async function cargar() {
    setLoading(true);
    try {
      const q = '?periodo=' + encodeURIComponent(periodo);
      const [resumen, activos] = await Promise.all([
        fetchJson('/api/portal/resumen' + q),
        fetchJson('/api/portal/activos' + q),
      ]);
      if (resumen && resumen.ok !== false) renderResumen(resumen);
      if (activos && activos.ok !== false) renderActivos(activos);
    } catch (e) {
      console.error('Portal SD Constructor', e);
    } finally {
      setLoading(false);
    }
  }

  root.querySelectorAll('[data-periodo]').forEach(function (btn) {
    btn.addEventListener('click', function () {
      periodo = btn.getAttribute('data-periodo') || 'mes';
      root.querySelectorAll('[data-periodo]').forEach(function (b) {
        b.classList.toggle('active', b === btn);
      });
      cargar();
    });
  });

  document.getElementById('tab-activos')?.addEventListener('shown.bs.tab', function () {
    /* datos ya cargados en paralelo */
  });

  cargar();
})();
