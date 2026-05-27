/**
 * Modal ficha Chilemat (imagen + descripción) — explorador y vinculación.
 */
(function (global) {
  'use strict';

  function esc(s) {
    const d = document.createElement('div');
    d.textContent = s == null ? '' : String(s);
    return d.innerHTML;
  }

  function ensureModal() {
    let el = document.getElementById('chmFichaModal');
    if (el) return el;
    el = document.createElement('div');
    el.id = 'chmFichaModal';
    el.className = 'modal fade';
    el.tabIndex = -1;
    el.innerHTML =
      '<div class="modal-dialog modal-lg modal-dialog-scrollable">' +
      '<div class="modal-content bg-dark text-light border-secondary">' +
      '<div class="modal-header border-secondary">' +
      '<h5 class="modal-title" id="chmFichaTitle">Ficha Chilemat</h5>' +
      '<button type="button" class="btn-close btn-close-white" data-bs-dismiss="modal"></button>' +
      '</div>' +
      '<div class="modal-body" id="chmFichaBody"><p class="text-muted">Cargando…</p></div>' +
      '<div class="modal-footer border-secondary">' +
      '<a href="#" id="chmFichaLink" class="btn btn-outline-info btn-sm" target="_blank" rel="noopener">Ver en chilemat.com</a>' +
      '<button type="button" class="btn btn-secondary btn-sm" data-bs-dismiss="modal">Cerrar</button>' +
      '</div></div></div>';
    document.body.appendChild(el);
    return el;
  }

  function renderFicha(data) {
    const img = data.imagen_url
      ? '<img src="' + esc(data.imagen_url) + '" alt="" class="img-fluid rounded mb-3" style="max-height:280px;object-fit:contain;background:#0f172a">'
      : '<p class="text-muted small">Sin imagen en catálogo web.</p>';
    const desc = data.descripcion_texto || data.descripcion_corta || '';
    const descHtml = data.descripcion_html
      ? '<div class="small border-top border-secondary pt-2 mt-2 chm-ficha-desc-html">' + data.descripcion_html + '</div>'
      : '';
    const meta =
      '<div class="small text-muted mb-2">' +
      'Ref web: <code>' + esc(data.product_reference || '—') + '</code> · VTEX ' +
      esc(data.vtex_product_id || '') +
      (data.fuente ? ' · ' + esc(data.fuente) : '') +
      '</div>';
    return (
      '<div class="row g-3">' +
      '<div class="col-md-5">' +
      img +
      '</div>' +
      '<div class="col-md-7">' +
      '<h6 class="fw-bold">' +
      esc(data.nombre || '') +
      '</h6>' +
      meta +
      '<p class="small">' +
      esc(desc) +
      '</p>' +
      descHtml +
      '</div></div>'
    );
  }

  function showModal(modalEl) {
    if (global.bootstrap && global.bootstrap.Modal) {
      global.bootstrap.Modal.getOrCreateInstance(modalEl).show();
    } else {
      modalEl.style.display = 'block';
      modalEl.classList.add('show');
    }
  }

  function applyFichaToModal(data) {
    const modalEl = ensureModal();
    const body = document.getElementById('chmFichaBody');
    const title = document.getElementById('chmFichaTitle');
    const linkBtn = document.getElementById('chmFichaLink');
    if (!data || !data.ok) {
      body.innerHTML =
        '<p class="text-danger">' + esc((data && data.error) || 'No se pudo cargar la ficha') + '</p>';
      return;
    }
    title.textContent = (data.nombre || 'Ficha Chilemat').slice(0, 80);
    body.innerHTML = renderFicha(data);
    linkBtn.classList.add('d-none');
    if (data.link) {
      linkBtn.href = data.link;
      linkBtn.classList.remove('d-none');
    }
  }

  function openFicha(vtexId, apiBase) {
    if (!vtexId) return;
    const modalEl = ensureModal();
    const body = document.getElementById('chmFichaBody');
    const title = document.getElementById('chmFichaTitle');
    body.innerHTML = '<p class="text-muted">Cargando ficha…</p>';
    title.textContent = 'Ficha Chilemat';
    showModal(modalEl);

    const url =
      (apiBase || '/api/compras/chilemat/ficha/') +
      encodeURIComponent(vtexId) +
      '?refresh=0';
    fetch(url, { credentials: 'same-origin', headers: { Accept: 'application/json' } })
      .then(function (r) {
        return r.json();
      })
      .then(function (d) {
        applyFichaToModal(d);
      })
      .catch(function () {
        body.innerHTML = '<p class="text-danger">Error de red al cargar ficha.</p>';
      });
  }

  function openProducto(productoId, apiBase) {
    const pid = parseInt(productoId, 10);
    if (!pid) return;
    const modalEl = ensureModal();
    const body = document.getElementById('chmFichaBody');
    const title = document.getElementById('chmFichaTitle');
    body.innerHTML = '<p class="text-muted">Cargando ficha…</p>';
    title.textContent = 'Ficha producto';
    showModal(modalEl);

    const url =
      (apiBase || '/api/pos/producto-ficha/') + pid + '?refresh=0';
    fetch(url, { credentials: 'same-origin', headers: { Accept: 'application/json' } })
      .then(function (r) {
        return r.json();
      })
      .then(function (d) {
        applyFichaToModal(d);
      })
      .catch(function () {
        body.innerHTML = '<p class="text-danger">Error de red al cargar ficha.</p>';
      });
  }

  function bindPosCartFichaButtons(root) {
    const scope = root || document;
    if (!global.__chmFichaDelegado) {
      global.__chmFichaDelegado = true;
      document.addEventListener(
        'click',
        function (e) {
          const btn = e.target && e.target.closest ? e.target.closest('.btn-pos-ficha-modal') : null;
          if (btn) {
            e.preventDefault();
            e.stopPropagation();
            const vtex = (btn.getAttribute('data-vtex-id') || '').trim();
            const pid = btn.getAttribute('data-producto-id');
            if (vtex) openFicha(vtex);
            else if (pid) openProducto(pid);
            return;
          }
          const a = e.target && e.target.closest ? e.target.closest('a.pos-cart-ficha-btn[href]') : null;
          if (a) {
            e.preventDefault();
            e.stopPropagation();
            const href = (a.getAttribute('href') || '').trim();
            if (href) global.open(href, '_blank', 'noopener');
          }
        },
        true
      );
    }
    scope.querySelectorAll('.btn-pos-ficha-modal').forEach(function (btn) {
      if (btn.dataset.chmFichaBound === '1') return;
      btn.dataset.chmFichaBound = '1';
      btn.addEventListener('click', function (e) {
        e.preventDefault();
        const vtex = (btn.getAttribute('data-vtex-id') || '').trim();
        const pid = btn.getAttribute('data-producto-id');
        if (vtex) {
          openFicha(vtex);
        } else if (pid) {
          openProducto(pid);
        }
      });
    });
  }

  global.ChilematFicha = {
    open: openFicha,
    openProducto: openProducto,
    render: renderFicha,
    bindPosCart: bindPosCartFichaButtons,
  };
})(typeof window !== 'undefined' ? window : this);
